# import os
# import joblib
# import numpy as np
# import pandas as pd
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
# from sklearn.model_selection import train_test_split, cross_val_score
# from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
# from sklearn.pipeline import Pipeline
# import pickle
# from datetime import datetime
# from typing import Dict, List, Tuple, Optional
# import json

# from app.config import settings
# from app.services.classifier import LEVEL2_CATEGORIES, LEVEL3_SUBCATEGORIES

# class ModelManager:
#     def __init__(self):
#         self.models = {
#             'level1': None,
#             'level2': None,
#             'level3': None
#         }
#         self.vectorizers = {
#             'level1': None,
#             'level2': None,
#             'level3': None
#         }
#         self.model_info = {
#             'level1': {'version': '1.0', 'accuracy': 0, 'trained_at': None},
#             'level2': {'version': '1.0', 'accuracy': 0, 'trained_at': None},
#             'level3': {'version': '1.0', 'accuracy': 0, 'trained_at': None}
#         }
#         self.load_models()

#     def load_models(self):
#         """Load pre-trained models if they exist"""
#         model_paths = {
#             'level1': settings.MODEL_LEVEL1_PATH,
#             'level2': settings.MODEL_LEVEL2_PATH,
#             'level3': settings.MODEL_LEVEL3_PATH
#         }

#         for level, path in model_paths.items():
#             if os.path.exists(path):
#                 try:
#                     with open(path, 'rb') as f:
#                         data = pickle.load(f)
#                         self.models[level] = data.get('model')
#                         self.vectorizers[level] = data.get('vectorizer')
#                         self.model_info[level] = data.get('info', self.model_info[level])
#                     print(f"Loaded {level} model from {path}")
#                 except Exception as e:
#                     print(f"Error loading {level} model: {e}")

#     def save_models(self):
#         """Save trained models"""
#         for level in ['level1', 'level2', 'level3']:
#             if self.models[level] and self.vectorizers[level]:
#                 path = getattr(settings, f'MODEL_{level.upper()}_PATH')

#                 # Update model info
#                 self.model_info[level]['version'] = f"{float(self.model_info[level]['version']) + 0.1:.1f}"
#                 self.model_info[level]['trained_at'] = datetime.utcnow().isoformat()

#                 data = {
#                     'model': self.models[level],
#                     'vectorizer': self.vectorizers[level],
#                     'info': self.model_info[level]
#                 }

#                 with open(path, 'wb') as f:
#                     pickle.dump(data, f)

#                 print(f"Saved {level} model to {path}")

#     def prepare_data(self, texts: List[str], labels: List) -> Tuple:
#         """Prepare data for training"""
#         X = np.array(texts)
#         y = np.array(labels)
#         return X, y

#     def train_level1(self, texts: List[str], labels: List[str], test_size=0.2):
#         """Train Level 1 classifier (Good/Bad)"""

#         # Convert labels to binary
#         y = [1 if label == 'bad' else 0 for label in labels]

#         # Split data
#         X_train, X_test, y_train, y_test = train_test_split(
#             texts, y, test_size=test_size, random_state=42, stratify=y
#         )

#         # Create pipeline
#         pipeline = Pipeline([
#             ('tfidf', TfidfVectorizer(max_features=5000, stop_words='english',
#                                       ngram_range=(1, 3), min_df=2, max_df=0.95)),
#             ('clf', RandomForestClassifier(n_estimators=100, max_depth=20,
#                                           random_state=42, class_weight='balanced'))
#         ])

#         # Train
#         pipeline.fit(X_train, y_train)

#         # Evaluate
#         y_pred = pipeline.predict(X_test)
#         accuracy = accuracy_score(y_test, y_pred)
#         precision = precision_score(y_test, y_pred)
#         recall = recall_score(y_test, y_pred)
#         f1 = f1_score(y_test, y_pred)

#         # Cross-validation
#         cv_scores = cross_val_score(pipeline, X_train, y_train, cv=5)

#         # Store model and vectorizer
#         self.models['level1'] = pipeline.named_steps['clf']
#         self.vectorizers['level1'] = pipeline.named_steps['tfidf']

#         # Update model info
#         self.model_info['level1'].update({
#             'accuracy': accuracy,
#             'precision': precision,
#             'recall': recall,
#             'f1_score': f1,
#             'cv_mean': cv_scores.mean(),
#             'cv_std': cv_scores.std(),
#             'training_samples': len(X_train),
#             'test_samples': len(X_test)
#         })

#         return {
#             'accuracy': accuracy,
#             'precision': precision,
#             'recall': recall,
#             'f1': f1,
#             'cv_scores': cv_scores.tolist()
#         }

#     def train_level2(self, texts: List[str], labels: List[str], test_size=0.2):
#         """Train Level 2 classifier (Main Categories)"""

#         # Map categories to indices
#         category_to_idx = {cat: i for i, cat in enumerate(LEVEL2_CATEGORIES.keys())}
#         y = [category_to_idx.get(label, 0) for label in labels]

#         # Split data
#         X_train, X_test, y_train, y_test = train_test_split(
#             texts, y, test_size=test_size, random_state=42, stratify=y if len(set(y)) > 1 else None
#         )

#         # Create pipeline
#         pipeline = Pipeline([
#             ('tfidf', TfidfVectorizer(max_features=5000, stop_words='english',
#                                       ngram_range=(1, 3), min_df=2, max_df=0.95)),
#             ('clf', RandomForestClassifier(n_estimators=150, max_depth=25,
#                                           random_state=42, class_weight='balanced'))
#         ])

#         # Train
#         pipeline.fit(X_train, y_train)

#         # Evaluate
#         y_pred = pipeline.predict(X_test)
#         accuracy = accuracy_score(y_test, y_pred)

#         # Store model and vectorizer
#         self.models['level2'] = pipeline.named_steps['clf']
#         self.vectorizers['level2'] = pipeline.named_steps['tfidf']

#         # Update model info
#         self.model_info['level2'].update({
#             'accuracy': accuracy,
#             'training_samples': len(X_train),
#             'test_samples': len(X_test),
#             'num_classes': len(set(y))
#         })

#         return {
#             'accuracy': accuracy,
#             'num_classes': len(set(y))
#         }

#     def train_level3(self, texts: List[str], labels: List[str], test_size=0.2):
#         """Train Level 3 classifier (Sub-categories)"""

#         # Map subcategories to indices
#         subcat_to_idx = {subcat: i for i, subcat in enumerate(LEVEL3_SUBCATEGORIES.keys())}
#         y = [subcat_to_idx.get(label, 0) for label in labels if label in subcat_to_idx]

#         if len(y) < 10:
#             return {'error': 'Insufficient training data'}

#         # Split data
#         X_train, X_test, y_train, y_test = train_test_split(
#             texts[:len(y)], y, test_size=test_size, random_state=42
#         )

#         # Create pipeline
#         pipeline = Pipeline([
#             ('tfidf', TfidfVectorizer(max_features=3000, stop_words='english',
#                                       ngram_range=(1, 2), min_df=2, max_df=0.95)),
#             ('clf', GradientBoostingClassifier(n_estimators=100, max_depth=15,
#                                               random_state=42))
#         ])

#         # Train
#         pipeline.fit(X_train, y_train)

#         # Evaluate
#         y_pred = pipeline.predict(X_test)
#         accuracy = accuracy_score(y_test, y_pred)

#         # Store model and vectorizer
#         self.models['level3'] = pipeline.named_steps['clf']
#         self.vectorizers['level3'] = pipeline.named_steps['tfidf']

#         # Update model info
#         self.model_info['level3'].update({
#             'accuracy': accuracy,
#             'training_samples': len(X_train),
#             'test_samples': len(X_test),
#             'num_classes': len(set(y))
#         })

#         return {
#             'accuracy': accuracy,
#             'num_classes': len(set(y))
#         }

#     def predict_level1(self, texts: List[str]) -> Tuple[List[str], List[float]]:
#         """Predict Level 1 categories"""
#         if not self.models['level1'] or not self.vectorizers['level1']:
#             return ['good'] * len(texts), [0.5] * len(texts)

#         X = self.vectorizers['level1'].transform(texts)
#         predictions = self.models['level1'].predict(X)
#         probabilities = self.models['level1'].predict_proba(X)

#         categories = ['bad' if p == 1 else 'good' for p in predictions]
#         confidences = [max(prob) for prob in probabilities]

#         return categories, confidences

#     def predict_level2(self, texts: List[str]) -> Tuple[List[str], List[float], List[Dict]]:
#         """Predict Level 2 categories"""
#         if not self.models['level2'] or not self.vectorizers['level2']:
#             return ['Unknown'] * len(texts), [0.0] * len(texts), [{}] * len(texts)

#         X = self.vectorizers['level2'].transform(texts)
#         predictions = self.models['level2'].predict(X)
#         probabilities = self.models['level2'].predict_proba(X)

#         categories = list(LEVEL2_CATEGORIES.keys())
#         predicted_cats = [categories[p] for p in predictions]
#         confidences = [max(prob) for prob in probabilities]

#         # Get all probabilities
#         all_scores = []
#         for prob in probabilities:
#             scores = {cat: float(prob[i]) for i, cat in enumerate(categories) if i < len(prob)}
#             all_scores.append(scores)

#         return predicted_cats, confidences, all_scores

#     def get_model_summary(self) -> Dict:
#         """Get summary of all models"""
#         return {
#             'level1': self.model_info['level1'],
#             'level2': self.model_info['level2'],
#             'level3': self.model_info['level3']
#         }

#     def export_model(self, level: str, path: str):
#         """Export model to file"""
#         if level in self.models and self.models[level]:
#             data = {
#                 'model': self.models[level],
#                 'vectorizer': self.vectorizers[level],
#                 'info': self.model_info[level]
#             }
#             with open(path, 'wb') as f:
#                 pickle.dump(data, f)
#             return True
#         return False

#     def import_model(self, level: str, path: str):
#         """Import model from file"""
#         if os.path.exists(path):
#             with open(path, 'rb') as f:
#                 data = pickle.load(f)
#                 self.models[level] = data.get('model')
#                 self.vectorizers[level] = data.get('vectorizer')
#                 self.model_info[level] = data.get('info', self.model_info[level])
#             return True
#         return False

# # Global model manager instance
# model_manager = ModelManager()

# def train_models(training_data: List[Dict]) -> Dict:
#     """Train all models with provided data"""
#     results = {}

#     # Prepare data
#     texts = [d['content'] for d in training_data]

#     # Train Level 1
#     level1_labels = [d['level1_category'] for d in training_data]
#     results['level1'] = model_manager.train_level1(texts, level1_labels)

#     # Train Level 2 (only bad comments)
#     bad_indices = [i for i, d in enumerate(training_data) if d['level1_category'] == 'bad']
#     if bad_indices:
#         bad_texts = [texts[i] for i in bad_indices]
#         level2_labels = [training_data[i]['level2_category'] for i in bad_indices]
#         results['level2'] = model_manager.train_level2(bad_texts, level2_labels)

#     # Train Level 3
#     level3_indices = [i for i in bad_indices if training_data[i].get('level3_subcategory')]
#     if level3_indices:
#         level3_texts = [texts[i] for i in level3_indices]
#         level3_labels = [training_data[i]['level3_subcategory'] for i in level3_indices]
#         results['level3'] = model_manager.train_level3(level3_texts, level3_labels)

#     # Save models
#     model_manager.save_models()

#     return results

# def load_models():
#     """Load all models"""
#     model_manager.load_models()
#     return model_manager