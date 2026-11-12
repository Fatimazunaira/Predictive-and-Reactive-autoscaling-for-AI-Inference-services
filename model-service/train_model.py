import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

texts = [
    "I love this product", "this is great", "amazing quality", "very happy with it",
    "excellent service", "works perfectly", "I hate this", "this is terrible",
    "awful quality", "very disappointed", "worst service ever", "it broke quickly",
]
labels = ["positive"] * 6 + ["negative"] * 6

model = make_pipeline(TfidfVectorizer(), LogisticRegression())
model.fit(texts, labels)

with open("model.pkl", "wb") as f:
    pickle.dump(model, f)