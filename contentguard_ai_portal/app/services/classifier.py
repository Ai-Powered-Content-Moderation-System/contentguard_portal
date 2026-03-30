
# app/services/classifier.py - Lightweight version without scikit-learn

import re
from typing import Dict, List, Tuple, Optional

# Category Definitions (kept for reference, but not used by ML)
LEVEL1_CATEGORIES = {"good": 0, "bad": 1}

LEVEL2_CATEGORIES = {
    "Harassment & Bullying": 1,
    "Hate Speech": 2,
    "Adult & Sexual Content": 3,
    "Child Safety": 4,
    "Violence & Gore": 5,
    "Self-Harm & Suicide": 6,
    "Spam & Manipulation": 7,
    "Political": 8,
    "Extremism & Terrorism": 9,
    "Misinformation": 10,
    "PII & Privacy": 11,
    "Illegal Goods & Services": 12,
    "Intellectual Property": 13,
    "Profanity & Vulgarity": 14,
    "Identity & Authenticity": 15,
    "National Integrity": 16
}

LEVEL3_SUBCATEGORIES = {
    # ... (same as before, omitted for brevity – keep your existing list)
}

class CommentClassifier:
    def __init__(self):
        # No models to load
        pass

    def load_models(self):
        """No-op"""
        pass

    def save_models(self):
        """No-op"""
        pass

    def preprocess_text(self, text: str) -> str:
        """Simple preprocessing (kept for compatibility)"""
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        text = re.sub(r'[^\w\s.,!?;:-]', ' ', text)
        text = ' '.join(text.split())
        return text

    def classify_comment(self, text: str) -> Dict:
        """
        Return dummy classification (all comments as 'good' with confidence 0.5).
        Level2 and Level3 are set to None (will appear as '-' in UI).
        """
        return {
            "level1": {
                "category": "good",
                "confidence": 0.5,
                "scores": {"good": 1.0}
            },
            "level2": {
                "category": None,
                "confidence": None,
                "scores": {}
            },
            "level3": {
                "category": None,
                "confidence": None,
                "scores": {}
            }
        }

    def retrain_with_feedback(self, training_data: List[Dict]) -> bool:
        """No-op: retraining not available"""
        return False

# Global classifier instance
classifier = CommentClassifier()