from typing import Dict
from connections.mongodb import MongoConnection


def insert_new_user_to_mongo(data: Dict):
    mongo_connection = MongoConnection('localhost:27017', 'mydatabase')
    collection = mongo_connection.collection_con('mycollection')

    collection.insert_one(data)
