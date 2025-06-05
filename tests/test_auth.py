from pymongo import MongoClient


def test_mongo():
    # Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017/")

    # Create or connect to a database
    db = client["mydatabase"]

    # Create or connect to a collection
    collection = db["mycollection"]

    # Verify the insertion
    for document in collection.find():
        print(document, flush=True)
