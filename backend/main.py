from fastapi import FastAPI

#upload server
app = FastAPI()

@app.get("/")
async def root():
    return {
        "project": "Toy Inventory AI System",
        "status": "online",
        "version": "1.0.0"
    }
