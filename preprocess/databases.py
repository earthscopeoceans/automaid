import os
import shutil
import json
import requests

DATABASE_LINK_NAME="Databases.json"

def update(path):
    network = 1
    print "************************"
    print "****Update Databases****"
    print "************************"
    link_path = os.path.join(path,DATABASE_LINK_NAME)
    try:
        request = requests.get('http://mermaid.osean.fr/databases/'+DATABASE_LINK_NAME,auth=('osean', 'osean3324'),timeout=10)
    except Exception as e:
        print "Exception: \""+ str(e) + "\" detected when get " + DATABASE_LINK_NAME
        network = 0
    else:
        if request.status_code == 200 :
            database_list = request.json()
            for database in database_list :
                if database["Name"]:
                    try:
                        new_req = requests.get('http://mermaid.osean.fr/databases/'+database["Name"],auth=('osean', 'osean3324'),timeout=10)
                        database["data"] = new_req.json()
                        if new_req.status_code != 200 :
                            print "Error " + str(new_req.status_code) + " when get " + database["Name"]
                            network = 0
                    except Exception as e:
                        print "Exception: \""+ str(e) + "\" detected when get " + str(database["Name"])
                        network = 0
        else:
            print "Error " + str(request.status_code) + " when get " + DATABASE_LINK_NAME
            network = 0

        if network > 0:
            if os.path.exists(path) :
                shutil.rmtree(path)
            os.makedirs(path)
            with open(link_path, 'w') as linkfile:
                json.dump(database_list, linkfile, indent=4)
            for database in database_list :
                if database["Name"]:
                    database_path = os.path.join(path,database["Name"])
                    with open(database_path, 'w') as databasefile:
                        json.dump(database["data"], databasefile)

if __name__ == "__main__":
    update("./databases/")
