from fastapi import FastAPI, File, UploadFile
import os
from datetime import datetime

#function for storing files in the folder /uploads
@app.post("/analyze")
async def Create_upload_file(file: UploadFile = File(description="A file read as UploadFile")):
 
 #reading file 
 contents = await file.read()

#storing file in folder
 with open("uploads/" + file.filename, "wb") as f:
    f.write(contents)

 return {"file_size": len(contents)}


#function for cleaning files which older than 14 days
@app.post("/uploads")
async def Clean_file():
  directory="uploads"
  files = os.listdir(directory)
  now = datetime.now()
#checking if folder exist
  if not os.path.exists(directory):
        return {"message": "Directory not found"}
  
#getting date time files
  for filename in files:
        path = os.path.join(directory, filename) 
        
        if os.path.isfile(path):
            t = os.path.getmtime(path)
            dt_object = datetime.fromtimestamp(t)
#checking if file older than 14 days
            if (now - dt_object).days >= 14:
                os.remove(path)
                print(f"Deleted: {filename}")

  return {"message": "Cleanup finished"}

