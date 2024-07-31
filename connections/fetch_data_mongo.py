# from connections.mongodb import MongoConnection


# class FetchDataMongo():


def find_user_by_strava_id(strava_id, collection):
    user = collection.find_one({"strava_id": strava_id})
    return user
