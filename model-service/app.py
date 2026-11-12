import pickle
import socket

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

with open("model.pkl", "rb") as f:
    model = pickle.load(f)


class Request(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(req: Request):
    label = model.predict([req.text])[0]
    return {"label": label, "replica": socket.gethostname()}