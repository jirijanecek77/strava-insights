from typing import Dict
import logging
from connections.mongodb import MongoConnection


def update_user_record(session, data_to_update: Dict):
    mongo_connection = MongoConnection("localhost:27017", "mydatabase")
    collection = mongo_connection.collection_con("mycollection")

    result = collection.update_one(
        {"strava_id": session["athlete"]["id"]},
        {"$set": data_to_update}
    )

    if result.matched_count > 0:
        logging.info(f"Successfully updated {result.modified_count} document(s).")
    else:
        logging.info("No document matched the filter criteria.")
