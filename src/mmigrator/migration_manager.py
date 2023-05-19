import os
from .db import connect_db
from .config_manager import ConfigManager
from .migration import Migration
from .constants import MMIGRATOR_COLLECTION


class MigrationManager(object):
    __db = None
    __config: dict = None
    __version: str = None
    __dist: str = None

    def __init__(self):
        MigrationManager.init()
        
        self.__config = ConfigManager.read_config()

        self.__dist = self.__config['dist']
        if not os.path.exists(self.__dist):
            os.mkdir(self.__dist)

        self.__db = connect_db(self.__config['connection'])
        
        if MMIGRATOR_COLLECTION not in self.__db.list_collection_names():
            self.__db.create_collection(MMIGRATOR_COLLECTION)
            self.__db[MMIGRATOR_COLLECTION].insert_one({'version': None})
        
        self.__version = self.__db[MMIGRATOR_COLLECTION].find_one()['version']

    @staticmethod
    def init():
        ConfigManager.init_config()

    def __get_files_list(self) -> (list[str], int):
        files = [f.rsplit(".")[0] for f in os.listdir(self.__dist)[::-1] if not f.startswith('__')]
        files = sorted(files, key=lambda x: int(x.split('_', 1)[0]))
        last_index = files.index(self.__version) if self.__version in files else -1

        return files, last_index

    def generate(self, name):
        mig = Migration(name=name, dist=self.__dist)
        mig.generate()
        
        print(f'\nSuccessfully created new migration {mig.name}\n')

    def revert(self):
        files, last_index = self.__get_files_list()
        prev_index = last_index-1

        if last_index < 0:
            print('No migrations to revert')
            return
        
        print('Reverting last migration...')

        file = files[last_index]

        mig = Migration(name=file, dist=self.__dist, db=self.__db)
        
        mig.revert()
        
        if last_index > 0:
            print(f'Current migration is...{files[prev_index]}')

        self.__version = files[prev_index] if last_index > 0 else None
        self.__persist_version()

    def migrate(self):
        files, last_index = self.__get_files_list()
        files = files[last_index + 1:]

        if len(files) == 0:
            print('No migrations to apply')
            return

        print('Running migrations...')

        try:
            for file in files:
                print(f'\tApplying {file}...')
    
                mig = Migration(
                    name=file,
                    dist=self.__dist,
                    db=self.__db
                )
    
                mig.migrate()

                self.__version = file
        except Exception as e:
            print(e)
        finally:
            self.__persist_version()

    def __persist_version(self):
        self.__db[MMIGRATOR_COLLECTION].update_one(
            {},
            {'$set': {'version': self.__version}}
        )
