from pymongo import MongoClient, errors
import logging


class MongoConnection:
    def __init__(self, host: str, database: str) -> None:
        """
        Initialize the MongoDB connection.

        :param host: MongoDB host address.
        :param database: Name of the database to connect to.
        """
        self.host = host
        self.database = database
        self.client = self._get_mongo_client()
        self.db_connection = self._get_db_connection()

    def _get_mongo_client(self) -> MongoClient:
        """
        Create a MongoDB client.

        :return: MongoClient instance.
        """
        try:
            client = MongoClient(f"mongodb://{self.host}/")
            return client
        except errors.ConnectionError as e:
            logging.error(f"Error connecting to MongoDB: {e}")
            raise

    def _get_db_connection(self):
        """
        Get the database connection.

        :return: Database connection object.
        """
        try:
            return self.client[self.database]
        except errors.InvalidName as e:
            logging.error(f"Invalid database name: {e}")
            raise

    def collection_con(self, collection: str):
        """
        Get a collection from the database.

        :param collection: Name of the collection.
        :return: Collection object.
        """
        try:
            return self.db_connection[collection]
        except errors.InvalidName as e:
            logging.error(f"Invalid collection name: {e}")
            raise
