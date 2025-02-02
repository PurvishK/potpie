import uvicorn
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from assignment_1.database.database import SessionLocal, init_db
from assignment_1.model.model import ReviewHistory, Category
from assignment_1.tasks.task import log_access
from sqlalchemy import func
from pydantic import BaseModel
from typing import List
import google.generativeai as genai
import json
from dotenv import load_dotenv
import os

load_dotenv()

gemini_key = os.getenv("GEMINI_KEY")

genai.configure(api_key=gemini_key)
model = genai.GenerativeModel("gemini-1.5-flash")

app = FastAPI()

# Initialize database
init_db()


class ReviewCategoryResponse(BaseModel):
    id: int
    name: str
    description: str
    average_stars: float
    total_reviews: int


class ReviewHistoryResponse(BaseModel):
    id: int
    text: str
    stars: int
    review_id: str
    created_at: str
    tone: str
    sentiment: str
    category_id: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tone_and_sentiment(review_text, review_starts, review_tone, review_sentiment):
    response = model.generate_content(f'''Below is the Review Details and Fill out the NULL values ( Null values in Review tone or Review Sentiment ) :
                            Review Description : {review_text}
                            Review Stars : {review_starts}
                            Review Tone : {review_tone}
                            Review Sentiment : {review_sentiment}
                            Just Give me Review Tone and Review Sentiment in JSON format
                            ''')
    data = json.loads(response.text.replace('json','').replace('```',''))
    return data['Review Tone'], data['Review Sentiment']


@app.get("/reviews/trends", response_model=List[ReviewCategoryResponse])
def get_reviews_trends(db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    trends = []

    for category in categories:
        reviews = db.query(ReviewHistory).filter(ReviewHistory.category_id == category.id).order_by(
            ReviewHistory.created_at.desc()).all()
        latest_review = reviews[0] if reviews else None
        if latest_review:
            avg_stars = db.query(func.avg(ReviewHistory.stars)).filter(
                ReviewHistory.category_id == category.id).scalar()
            total_reviews = db.query(ReviewHistory).filter(ReviewHistory.category_id == category.id).count()
            trends.append({
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "average_stars": avg_stars,
                "total_reviews": total_reviews
            })

    # Sort categories by average stars in descending order
    trends = sorted(trends, key=lambda x: x['average_stars'], reverse=True)[:5]

    # Log the access asynchronously
    log_access.apply_async(args=["GET /reviews/trends"])

    return trends


@app.get("/reviews/", response_model=List[ReviewHistoryResponse])
def get_reviews(category_id: int, db: Session = Depends(get_db)):

    reviews = db.query(ReviewHistory).filter(ReviewHistory.category_id == category_id).order_by(
        ReviewHistory.created_at.desc()).all()

    reviews_response = []
    for review in reviews:
        
        if not review.tone or not review.sentiment:
            tone, sentiment = get_tone_and_sentiment(review.text, review.stars, review.tone, review.sentiment)
            review.tone = tone
            review.sentiment = sentiment

        reviews_response.append({
            "id": review.id,
            "text": review.text,
            "stars": review.stars,
            "review_id": review.review_id,
            "created_at": review.created_at.isoformat(),
            "tone": review.tone,
            "sentiment": review.sentiment,
            "category_id": review.category_id
        })

    # Log the access asynchronously
    log_access.apply_async(args=[f"GET /reviews/?category_id={category_id}"])

    return reviews_response


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
