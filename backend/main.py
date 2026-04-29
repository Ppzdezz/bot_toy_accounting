from fastapi import FastAPI

#upload server
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
