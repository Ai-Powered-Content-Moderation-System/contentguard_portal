# from router/extraction.py

# async def process_youtube_extraction(
#     job_id: str,
#     url: str,
#     max_comments: int,
#     include_replies: bool,
#     apply_classification: bool,
#     username: str
# ):
#     """Background task for YouTube extraction with better error handling"""

#     logger.info(f"Starting YouTube extraction job {job_id} for URL: {url}")

#     db = next(get_db())
#     job = db.query(ExtractionJob).filter(ExtractionJob.job_id == job_id).first()

#     try:
#         # Update job status
#         job.status = "processing"
#         job.started_at = datetime.utcnow()
#         db.commit()
#         logger.info(f"Job {job_id} status updated to processing")

#         # Extract video info
#         try:
#             logger.info(f"Extracting video info for {url}")
#             video_info = await youtube_extractor.extract_video_info(url)
#             if not video_info:
#                 raise Exception("Failed to extract video info - video might be private or unavailable")

#             job.video_id = video_info.get("id")
#             job.video_title = video_info.get("title", "Unknown Title")
#             job.video_channel = video_info.get("uploader", "Unknown Channel")
#             job.video_duration = video_info.get("duration", 0)
#             db.commit()
#             logger.info(f"Video info extracted: {job.video_title}")
#         except Exception as e:
#             logger.error(f"Error extracting video info: {str(e)}")
#             raise Exception(f"Failed to extract video info: {str(e)}")

#         # Extract comments
#         try:
#             logger.info(f"Extracting comments (max: {max_comments}, include_replies: {include_replies})")
#             comments = await youtube_extractor.extract_comments(url, max_comments)

#             if not comments:
#                 logger.warning("No comments extracted from video")
#                 job.total_comments = 0
#                 job.extracted_comments = 0
#             else:
#                 job.total_comments = len(comments)
#                 logger.info(f"Extracted {len(comments)} comments")

#             db.commit()
#         except Exception as e:
#             logger.error(f"Error extracting comments: {str(e)}")
#             raise Exception(f"Failed to extract comments: {str(e)}")

#         # Process each comment
#         if comments:
#             for i, comment_data in enumerate(comments):
#                 try:
#                     # Apply classification if requested
#                     if apply_classification:
#                         try:
#                             classification = classifier.classify_comment(comment_data["content"])
#                             comment_data.update(classification)
#                         except Exception as e:
#                             logger.error(f"Error classifying comment {i}: {str(e)}")
#                             # Continue without classification
#                             pass

#                     # Encrypt content
#                     try:
#                         encrypted_content = encrypt_content(comment_data["content"])
#                     except Exception as e:
#                         logger.error(f"Error encrypting comment {i}: {str(e)}")
#                         encrypted_content = comment_data["content"]  # Fallback

#                     # Create comment record
#                     comment = Comment(
#                         comment_id=comment_data.get("comment_id", str(uuid.uuid4())),
#                         content=encrypted_content,
#                         content_hash=hashlib.sha256(comment_data["content"].encode()).hexdigest(),
#                         content_length=len(comment_data["content"]),
#                         author=comment_data.get("author", "Unknown"),
#                         author_id=comment_data.get("author_id"),
#                         video_id=job.video_id,
#                         video_title=job.video_title,
#                         video_url=url,
#                         video_channel=job.video_channel,
#                         published_at=datetime.fromtimestamp(comment_data["published_at"]) if comment_data.get("published_at") else None,
#                         like_count=comment_data.get("like_count", 0),
#                         reply_count=comment_data.get("reply_count", 0),
#                         is_reply=comment_data.get("is_reply", False),
#                         parent_id=comment_data.get("parent_id"),

#                         # Classification results
#                         level1_category=comment_data.get("level1", {}).get("category"),
#                         level1_confidence=comment_data.get("level1", {}).get("confidence", 0),
#                         level2_category=comment_data.get("level2", {}).get("category"),
#                         level2_confidence=comment_data.get("level2", {}).get("confidence", 0),
#                         level3_subcategory=comment_data.get("level3", {}).get("category"),
#                         level3_confidence=comment_data.get("level3", {}).get("confidence", 0),

#                         # Source info
#                         source="youtube",
#                         source_level=1,
#                         extraction_job_id=job_id
#                     )

#                     db.add(comment)
#                     db.flush()  # Flush to get the ID

#                     # Update job statistics
#                     if comment.level1_category == "good":
#                         job.good_comments += 1
#                     elif comment.level1_category == "bad":
#                         job.bad_comments += 1
#                         if comment.level2_category:
#                             if not job.categories_found:
#                                 job.categories_found = {}
#                             job.categories_found[comment.level2_category] = job.categories_found.get(comment.level2_category, 0) + 1

#                     job.extracted_comments += 1

#                     # Create extracted data record
#                     try:
#                         extracted = ExtractedData(
#                             job_id=job_id,
#                             comment_id=comment.comment_id,
#                             raw_data=comment_data,
#                             extraction_method="youtube_dlp"
#                         )
#                         db.add(extracted)
#                     except Exception as e:
#                         logger.error(f"Error creating ExtractedData for comment {i}: {str(e)}")

#                     # Update progress every 10 comments
#                     if i % 10 == 0 and job.total_comments > 0:
#                         job.progress = (i / job.total_comments) * 100
#                         db.commit()
#                         logger.info(f"Progress: {job.progress:.1f}% ({i}/{job.total_comments})")

#                 except Exception as e:
#                     job.failed_comments += 1
#                     logger.error(f"Error processing comment {i}: {str(e)}")
#                     logger.error(traceback.format_exc())

#             db.commit()

#             # Save to CSV
#             try:
#                 output_file = f"exports/youtube_extract_{job_id}.csv"
#                 os.makedirs("exports", exist_ok=True)

#                 # Get all comments for this job
#                 job_comments = db.query(Comment).filter(Comment.extraction_job_id == job_id).all()

#                 # Prepare CSV data
#                 import pandas as pd
#                 data = []
#                 for c in job_comments:
#                     try:
#                         decrypted = decrypt_content(c.content)
#                     except:
#                         decrypted = "[Encrypted]"

#                     data.append({
#                         "comment_id": c.comment_id,
#                         "author": c.author,
#                         "content": decrypted,
#                         "published_at": c.published_at,
#                         "like_count": c.like_count,
#                         "level1": c.level1_category,
#                         "level1_conf": c.level1_confidence,
#                         "level2": c.level2_category,
#                         "level2_conf": c.level2_confidence,
#                         "level3": c.level3_subcategory,
#                         "level3_conf": c.level3_confidence
#                     })

#                 if data:
#                     df = pd.DataFrame(data)
#                     df.to_csv(output_file, index=False, encoding='utf-8-sig')
#                     job.output_file = output_file
#                     logger.info(f"CSV file saved: {output_file}")
#                 else:
#                     logger.warning("No data to save to CSV")

#             except Exception as e:
#                 logger.error(f"Error saving CSV: {str(e)}")

#         # Update job
#         job.status = "completed"
#         job.completed_at = datetime.utcnow()
#         job.progress = 100
#         db.commit()
#         logger.info(f"Job {job_id} completed successfully")

#     except Exception as e:
#         job.status = "failed"
#         job.error_message = str(e)
#         job.error_details = {"traceback": traceback.format_exc()}
#         db.commit()
#         logger.error(f"Job {job_id} failed: {str(e)}")
#         logger.error(traceback.format_exc())
#     finally:
#         db.close()

# async def process_youtube_extraction(
#     job_id: str,
#     url: str,
#     max_comments: int,
#     include_replies: bool,
#     apply_classification: bool,
#     username: str
# ):
#     """Background task for YouTube extraction"""

#     db = next(get_db())
#     job = db.query(ExtractionJob).filter(ExtractionJob.job_id == job_id).first()

#     try:
#         # Update job status
#         job.status = "processing"
#         job.started_at = datetime.utcnow()
#         db.commit()

#         # Extract video info
#         video_info = await youtube_extractor.extract_video_info(url)
#         job.video_id = video_info.get("id")
#         job.video_title = video_info.get("title")
#         job.video_channel = video_info.get("uploader")
#         job.video_duration = video_info.get("duration", 0)
#         db.commit()

#         # Extract comments
#         comments = await youtube_extractor.extract_comments(url, max_comments)
#         job.total_comments = len(comments)
#         db.commit()

#         # Process each comment
#         for i, comment_data in enumerate(comments):
#             try:
#                 # Apply classification if requested
#                 if apply_classification:
#                     classification = classifier.classify_comment(comment_data["content"])
#                     comment_data.update(classification)

#                 # Encrypt content
#                 encrypted_content = encrypt_content(comment_data["content"])

#                 # Create comment record
#                 comment = Comment(
#                     comment_id=comment_data.get("comment_id", str(uuid.uuid4())),
#                     content=encrypted_content,
#                     content_hash=hashlib.sha256(comment_data["content"].encode()).hexdigest(),
#                     content_length=len(comment_data["content"]),
#                     author=comment_data.get("author"),
#                     author_id=comment_data.get("author_id"),
#                     video_id=job.video_id,
#                     video_title=job.video_title,
#                     video_url=url,
#                     video_channel=job.video_channel,
#                     published_at=datetime.fromtimestamp(comment_data["published_at"]) if comment_data.get("published_at") else None,
#                     like_count=comment_data.get("like_count", 0),
#                     reply_count=comment_data.get("reply_count", 0),
#                     is_reply=comment_data.get("is_reply", False),
#                     parent_id=comment_data.get("parent_id"),

#                     # Classification results
#                     level1_category=comment_data.get("level1", {}).get("category"),
#                     level1_confidence=comment_data.get("level1", {}).get("confidence", 0),
#                     level2_category=comment_data.get("level2", {}).get("category"),
#                     level2_confidence=comment_data.get("level2", {}).get("confidence", 0),
#                     level3_subcategory=comment_data.get("level3", {}).get("category"),
#                     level3_confidence=comment_data.get("level3", {}).get("confidence", 0),

#                     # Source info
#                     source="youtube",
#                     source_level=1,
#                     extraction_job_id=job_id
#                 )

#                 db.add(comment)
#                 db.flush()  # Flush to get the ID

#                 # Update job statistics
#                 if comment.level1_category == "good":
#                     job.good_comments += 1
#                 elif comment.level1_category == "bad":
#                     job.bad_comments += 1
#                     if comment.level2_category:
#                         # Use a method to add category count or handle it differently
#                         if not job.categories_found:
#                             job.categories_found = {}
#                         job.categories_found[comment.level2_category] = job.categories_found.get(comment.level2_category, 0) + 1

#                 job.extracted_comments += 1

#                 # Create extracted data record
#                 extracted = ExtractedData(
#                     job_id=job_id,
#                     comment_id=comment.comment_id,
#                     raw_data=comment_data,
#                     extraction_method="youtube_dlp"
#                 )
#                 db.add(extracted)

#                 # Update progress every 10 comments
#                 if i % 10 == 0:
#                     job.progress = (i / len(comments)) * 100
#                     db.commit()

#             except Exception as e:
#                 job.failed_comments += 1
#                 print(f"Error processing comment: {e}")

#         # Save to CSV
#         output_file = f"exports/youtube_extract_{job_id}.csv"
#         os.makedirs("exports", exist_ok=True)

#         # Get all comments for this job
#         job_comments = db.query(Comment).filter(Comment.extraction_job_id == job_id).all()

#         # Prepare CSV data
#         import pandas as pd
#         data = []
#         for c in job_comments:
#             try:
#                 decrypted = decrypt_content(c.content)
#             except:
#                 decrypted = "[Encrypted]"

#             data.append({
#                 "comment_id": c.comment_id,
#                 "author": c.author,
#                 "content": decrypted,
#                 "published_at": c.published_at,
#                 "like_count": c.like_count,
#                 "level1": c.level1_category,
#                 "level1_conf": c.level1_confidence,
#                 "level2": c.level2_category,
#                 "level2_conf": c.level2_confidence,
#                 "level3": c.level3_subcategory,
#                 "level3_conf": c.level3_confidence
#             })

#         df = pd.DataFrame(data)
#         df.to_csv(output_file, index=False, encoding='utf-8-sig')

#         # Update job
#         job.status = "completed"
#         job.completed_at = datetime.utcnow()
#         job.progress = 100
#         job.output_file = output_file
#         db.commit()

#     except Exception as e:
#         job.status = "failed"
#         job.error_message = str(e)
#         db.commit()
#     finally:
#         db.close()
# async def process_youtube_extraction(
#     job_id: str,
#     url: str,
#     max_comments: int,
#     include_replies: bool,
#     apply_classification: bool,
#     username: str
# ):
#     """Background task for YouTube extraction with timeout"""

#     logger.info(f"Starting YouTube extraction job {job_id} for URL: {url}")

#     db = next(get_db())
#     job = db.query(ExtractionJob).filter(ExtractionJob.job_id == job_id).first()

#     try:
#         # Update job status
#         job.status = "processing"
#         job.started_at = datetime.utcnow()
#         db.commit()
#         logger.info(f"Job {job_id} status updated to processing")

#         # Extract video info
#         try:
#             logger.info(f"Extracting video info for {url}")
#             video_info = await youtube_extractor.extract_video_info(url)
#             if not video_info:
#                 raise Exception("Failed to extract video info - video might be private or unavailable")

#             job.video_id = video_info.get("id")
#             job.video_title = video_info.get("title", "Unknown Title")
#             job.video_channel = video_info.get("uploader", "Unknown Channel")
#             job.video_duration = video_info.get("duration", 0)
#             db.commit()
#             logger.info(f"Video info extracted: {job.video_title}")
#         except Exception as e:
#             logger.error(f"Error extracting video info: {str(e)}")
#             raise Exception(f"Failed to extract video info: {str(e)}")

#         # Extract comments with timeout
#         try:
#             logger.info(f"Extracting comments (max: {max_comments}, include_replies: {include_replies})")
#             logger.info("This may take a while for videos with many comments...")

#             # Add timeout of 2 minutes for comment extraction
#             import asyncio
#             comments = await asyncio.wait_for(
#                 youtube_extractor.extract_comments(url, max_comments),
#                 timeout=120  # 2 minutes timeout
#             )

#             if not comments:
#                 logger.warning("No comments extracted from video")
#                 job.total_comments = 0
#                 job.extracted_comments = 0
#             else:
#                 job.total_comments = len(comments)
#                 logger.info(f"Extracted {len(comments)} comments")

#             db.commit()
#         except asyncio.TimeoutError:
#             logger.error("Comment extraction timed out after 2 minutes")
#             job.status = "failed"
#             job.error_message = "Comment extraction timed out. Try with fewer comments or a different video."
#             db.commit()
#             return
#         except Exception as e:
#             logger.error(f"Error extracting comments: {str(e)}")
#             raise Exception(f"Failed to extract comments: {str(e)}")

#         # Process each comment
#         if comments:
#             for i, comment_data in enumerate(comments):
#                 try:
#                     # ... rest of processing code ...

#                     # Update progress more frequently
#                     if i % 5 == 0 and job.total_comments > 0:
#                         job.progress = (i / job.total_comments) * 100
#                         db.commit()
#                         logger.info(f"Progress: {job.progress:.1f}% ({i}/{job.total_comments})")

#                 except Exception as e:
#                     job.failed_comments += 1
#                     logger.error(f"Error processing comment {i}: {str(e)}")

#             db.commit()

#             # Save to CSV
#             try:
#                 output_file = f"exports/youtube_extract_{job_id}.csv"
#                 os.makedirs("exports", exist_ok=True)

#                 # ... CSV saving code ...

#             except Exception as e:
#                 logger.error(f"Error saving CSV: {str(e)}")

#         # Update job
#         job.status = "completed"
#         job.completed_at = datetime.utcnow()
#         job.progress = 100
#         db.commit()
#         logger.info(f"Job {job_id} completed successfully")

#     except Exception as e:
#         job.status = "failed"
#         job.error_message = str(e)
#         job.error_details = {"traceback": traceback.format_exc()}
#         db.commit()
#         logger.error(f"Job {job_id} failed: {str(e)}")
#         logger.error(traceback.format_exc())
#     finally:
#         db.close()