from fastapi import FastAPI
import os

app = FastAPI()


@app.get("/")
def check_file():
    filepath = "hello_word.txt"
    if os.path.exists(filepath):
        with open(filepath) as f:
            contents = f.read().strip("\n")
            message = f"Your file exists. Its contents are: '{contents}'"
            return {"message": message}
    else:
        return {"message": "File is missing."}