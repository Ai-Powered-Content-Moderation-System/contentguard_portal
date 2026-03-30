# v2
# app/models/__init__.py

from app.models.database import (
    Base,
    User,
    Comment,
    TrainingData,
    get_db,
    init_db
)

from app.models.extraction import (
    ExtractionJob,
    ExtractionPattern,
    ExtractedData,
    init_extraction_tables
)

__all__ = [
    'Base',
    'User',
    'Comment',
    'TrainingData',
    'ExtractionJob',
    'ExtractionPattern',
    'ExtractedData',
    'get_db',
    'init_db',
    'init_extraction_tables'
]

