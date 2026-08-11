from flask import Blueprint


internships_bp = Blueprint(
    'internships',
    __name__,
    url_prefix='/internships'
)

from app.internships import routes
