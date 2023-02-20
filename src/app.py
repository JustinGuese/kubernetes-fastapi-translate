from hashlib import sha256
from os import environ

import deepl
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient

load_dotenv("../.env")

app = FastAPI()

environ["DB_NAME"] = "translations"

@app.on_event("startup")
def startup_db_client():
    app.mongodb_client = MongoClient(environ["MONGODB_URI"])
    app.database = app.mongodb_client[environ["DB_NAME"]]
    app.collection = app.database["translations"]
    app.deeplclient = deepl.Translator(environ["DEEPLKEY"]) 


@app.on_event("shutdown")
def shutdown_db_client():
    app.mongodb_client.close()
    
async def checkAuthToken(token: str):
    if token == environ["AUTHTOKEN"]:
        return True
    raise HTTPException(status_code=401, detail="Invalid auth token")
    
async def getDeeplTranslation(sentence: str, tolang: str):
    key = sha256(sentence.encode()).hexdigest()
    mongoresult = app.collection.find_one({"_id": key})
    if mongoresult:
        # check if we have that language
        res = mongoresult.get(tolang)
        if res is not None:
            return res
    # else we need to query deepl
    print("info: didnt find translation, query deepl", sentence, tolang)
    result = app.deeplclient.translate_text(sentence, target_lang=tolang) 
    translated_text = result.text
    if mongoresult:
        # update pymongo database with this language
        
        app.collection.update_one({"_id": key}, {"$set": {tolang: translated_text}}, upsert=True)
    else:
        app.collection.insert_one({"_id": key, tolang: translated_text, "EN": sentence})
    return translated_text
    
@app.get("/")
async def getTranslation(sentence: str, tolang: str, token: str):
    await checkAuthToken(token)
    breaksentences = sentence.split("\n")
    for i, sentence in enumerate(breaksentences):
        dotsentences = sentence.split(".")
        for j,dot in enumerate(dotsentences):
            commasentences = dot.split(",")
            for k, sentence in enumerate(commasentences):
                if len(sentence) > 0:
                    commasentences[k] = await getDeeplTranslation(sentence, tolang)
            dotsentences[j] = ",".join(commasentences)
        breaksentences[i] = ".".join(dotsentences)
    return "\n".join(breaksentences)