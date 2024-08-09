from connections.mongodb import MongoConnection


def find_user_by_strava_id(strava_id):
    mongo_connection = MongoConnection('localhost:27017', 'mydatabase')
    collection = mongo_connection.collection_con('mycollection')

    user = collection.find_one({"strava_id": strava_id})
    return user
