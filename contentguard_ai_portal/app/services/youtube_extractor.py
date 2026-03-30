# app/services/youtube_extractor.py - Enhanced version with progress tracking

import yt_dlp
import asyncio
from typing import List, Dict, Optional
import logging
import uuid
import time

logger = logging.getLogger(__name__)

class YouTubeExtractor:
    def __init__(self):
        self.ydl_opts = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            'ignoreerrors': True,
        }
        self.progress_callbacks = {}

    def register_progress_callback(self, job_id: str, callback_func):
        """Register a callback function for progress updates"""
        self.progress_callbacks[job_id] = callback_func

    def unregister_progress_callback(self, job_id: str):
        """Remove progress callback"""
        if job_id in self.progress_callbacks:
            del self.progress_callbacks[job_id]

    def _progress_hook(self, d):
        """Progress hook for yt-dlp"""
        if d['status'] == 'downloading':
            # Extract info from yt-dlp progress
            if 'info_dict' in d:
                info = d['info_dict']
                if 'comment_count' in info:
                    # This is a comment download progress
                    filename = d.get('filename', '')
                    if 'comment' in filename.lower():
                        # Parse which comment thread is being downloaded
                        logger.info(f"yt-dlp: {d.get('_percent_str', '0%')} - {d.get('info_dict', {}).get('title', '')[:50]}")

    async def extract_video_info(self, url: str) -> Dict:
        """Extract video information using yt-dlp"""
        try:
            loop = asyncio.get_event_loop()

            def _extract():
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            info = await loop.run_in_executor(None, _extract)

            if not info:
                logger.error(f"No video info extracted for {url}")
                return {}

            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "uploader": info.get("uploader"),
                "uploader_id": info.get("uploader_id"),
                "upload_date": info.get("upload_date"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "comment_count": info.get("comment_count", 0),
                "description": info.get("description"),
                "tags": info.get("tags", []),
                "categories": info.get("categories", [])
            }
        except Exception as e:
            logger.error(f"Error extracting video info: {str(e)}")
            return {}

    async def extract_comments(self, url: str, max_comments: int = 500, job_id: str = None) -> List[Dict]:
        """Extract comments from YouTube video with detailed progress"""
        comments = []

        ydl_opts = {
            **self.ydl_opts,
            'getcomments': True,
            'extract_flat': False,
            'max_comments': max_comments,
            'ignoreerrors': True,
            'extractor_args': {
                'youtube': {
                    'max_comments': [str(max_comments)],
                    'comment_sort': ['top'],  # Get top comments first for faster results
                }
            }
        }

        try:
            loop = asyncio.get_event_loop()

            def _extract_comments():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Add progress hook
                    ydl.add_progress_hook(self._progress_hook)
                    return ydl.extract_info(url, download=False)

            logger.info(f"Starting comment extraction for {url}")
            start_time = time.time()

            info = await loop.run_in_executor(None, _extract_comments)

            elapsed = time.time() - start_time
            logger.info(f"Comment extraction completed in {elapsed:.2f} seconds")

            if not info:
                logger.error(f"No video info extracted for {url}")
                return []

            video_id = info.get("id")
            video_title = info.get("title", "Unknown Title")
            total_comments_found = info.get("comment_count", 0)

            logger.info(f"Video has approximately {total_comments_found} total comments")

            if 'comments' in info and info['comments']:
                logger.info(f"Retrieved {len(info['comments'])} top-level comments")

                # Process top-level comments
                for idx, comment in enumerate(info['comments']):
                    try:
                        if len(comments) >= max_comments:
                            logger.info(f"Reached max comments limit ({max_comments})")
                            break

                        comment_data = {
                            "comment_id": comment.get("id", str(uuid.uuid4())),
                            "video_id": video_id,
                            "video_title": video_title,
                            "author": comment.get("author"),
                            "author_id": comment.get("author_id"),
                            "content": comment.get("text", ""),
                            "published_at": comment.get("timestamp"),
                            "like_count": comment.get("like_count", 0),
                            "reply_count": comment.get("reply_count", 0),
                            "is_reply": False,
                            "parent_id": None
                        }

                        comments.append(comment_data)

                        # Process replies if any and if we haven't hit the limit
                        if 'replies' in comment and comment['replies'] and len(comments) < max_comments:
                            for reply_idx, reply in enumerate(comment['replies']):
                                if len(comments) >= max_comments:
                                    break

                                reply_data = {
                                    "comment_id": reply.get("id", str(uuid.uuid4())),
                                    "video_id": video_id,
                                    "video_title": video_title,
                                    "author": reply.get("author"),
                                    "author_id": reply.get("author_id"),
                                    "content": reply.get("text", ""),
                                    "published_at": reply.get("timestamp"),
                                    "like_count": reply.get("like_count", 0),
                                    "reply_count": 0,
                                    "is_reply": True,
                                    "parent_id": comment.get("id")
                                }
                                comments.append(reply_data)

                        # Send progress update every 10 comments
                        if (idx + 1) % 10 == 0 and job_id and job_id in self.progress_callbacks:
                            progress = min(100, (len(comments) / max_comments) * 100)
                            self.progress_callbacks[job_id]({
                                "stage": "extracting",
                                "progress": progress,
                                "current": len(comments),
                                "total": max_comments,
                                "message": f"Extracted {len(comments)}/{max_comments} comments"
                            })

                    except Exception as e:
                        logger.error(f"Error processing comment {idx}: {str(e)}")
                        continue

            logger.info(f"Total comments extracted: {len(comments)}")
            return comments

        except Exception as e:
            logger.error(f"Error extracting comments: {str(e)}")
            return []

# Initialize extractor
youtube_extractor = YouTubeExtractor()
# Initialize extractor
