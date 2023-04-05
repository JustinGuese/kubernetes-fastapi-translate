from hashlib import sha256
from os import environ

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient

load_dotenv("../.env")

MODEL = "gpt-3.5-turbo"
TOTALCOST = 0.

app = FastAPI()

environ["DB_NAME"] = "translations"

TOLANG = {
    "DE" : "German",
    "FR" : "French",
    "ES" : "Spanish",
    "IT" : "Italian",
    "NL" : "Dutch",
}

@app.on_event("startup")
def startup_db_client():
    app.mongodb_client = MongoClient(environ["MONGODB_URI"])
    app.database = app.mongodb_client[environ["DB_NAME"]]
    app.collection = app.database["translations"]
    


@app.on_event("shutdown")
def shutdown_db_client():
    app.mongodb_client.close()
    
async def checkAuthToken(token: str):
    if token == environ["AUTHTOKEN"]:
        return True
    raise HTTPException(status_code=401, detail="Invalid auth token")
    
# async def getDeeplTranslation(sentence: str, tolang: str):
#     key = sha256(sentence.encode()).hexdigest()
#     mongoresult = app.collection.find_one({"_id": key})
#     if mongoresult:
#         # check if we have that language
#         res = mongoresult.get(tolang)
#         if res is not None:
#             return res
#     # else we need to query deepl
#     print("info: didnt find translation, query deepl", sentence, tolang)
#     result = app.deeplclient.translate_text(sentence, target_lang=tolang) 
#     translated_text = result.text
#     if mongoresult:
#         # update pymongo database with this language
        
#         app.collection.update_one({"_id": key}, {"$set": {tolang: translated_text}}, upsert=True)
#     else:
#         app.collection.insert_one({"_id": key, tolang: translated_text, "EN": sentence})
#     return translated_text
async def getGPTTranslation(sentence: str, tolang: str):
    key = sha256(sentence.encode()).hexdigest()
    mongoresult = app.collection.find_one({"_id": key})
    if mongoresult:
        # check if we have that language
        res = mongoresult.get(tolang)
        if res is not None:
            return res
    # else we need to query deepl
    print("info: didnt find translation, query gpt", sentence, TOLANG[tolang])
    prompt = f"Translate the following sentence after the ':' from English to {TOLANG[tolang]}. Just return the 1:1 translation and no other comments:\n{sentence}"
    response = openai.ChatCompletion.create(
        model = MODEL,
        messages = [{"role":"system","content":prompt}]
        )
    translated_text = response["choices"][0]["message"]["content"].replace(".,",",") # fix weird gpt quirks
    usage = response["usage"]["total_tokens"]
    TOTALCOST += usage/1000*0.002
    print("crnt totalcost %.2f$ since startup - i got the translation: %s" % (TOTALCOST, translated_text))
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
                    commasentences[k] = await getGPTTranslation(sentence, tolang)
            dotsentences[j] = ",".join(commasentences)
        breaksentences[i] = ".".join(dotsentences)
    return "\n".join(breaksentences)