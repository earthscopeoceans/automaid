import os
import shutil
from string import maketrans
import sys
import glob
import struct
import json
import re
import time
import traceback

#1:CLIENT
#2:SUPERUSERS
#3:ADMINISTRATOR
user_level = 1

# Get database name with link file and version read on file
def get_database_version(file_version,model) :
    absFilePath = os.path.abspath(__file__)
    scriptpath, scriptfilename = os.path.split(absFilePath)
    database_path = os.path.join(scriptpath,"databases/Databases.json")
    if os.path.exists(database_path):
        with open(database_path,"r") as f:
            databases = json.loads(f.read())
        # get major and minor versions
        file_version=file_version.split(".")
        file_major = 2
        file_minor = 17
        if file_version[0] :
            file_major = int(file_version[0])
        if file_version[1] :
            file_minor = int(file_version[1])
        print "file version : " + str(file_major) +"."+ str(file_minor)
        for database in databases :
            #print "Model : " + str(database["Model"])
            if not database["Model"] or (model == database["Model"]):
                database_minor_max = 2147483647
                database_major_max = 2147483647
                databaseMin_version = database["MinVersion"].split(".")
                database_major_min = int(databaseMin_version[0])
                database_minor_min = int(databaseMin_version[1])
                if database["MaxVersion"] != "None":
                    databaseMax_version = database["MaxVersion"].split(".")
                    database_major_max = int(databaseMax_version[0])
                    database_minor_max = int(databaseMax_version[1])
                #print "MAJOR MAX : " + str(database_major_max)
                #print "MAJOR MIN : " + str(database_major_min)
                #print "MINOR MAX : " +str(database_minor_max)
                #print "MINOR MIN : " +str(database_minor_min)
                if ((file_major > database_major_min) and (file_major < database_minor_max)) \
                or ((file_major >= database_major_min) and (file_major <= database_major_max) \
                and (file_minor >= database_minor_min) and (file_minor <= database_minor_max)) :
                    print database["Name"]
                    return database["Name"]
                #print "\r\n"
        print "No Database available for : " + str(file_version)
        return ""
    else :
        print "no databases file : " + database_path
        return ""
# Concatenate .000 files .BIN files in the path
def concatenate_bin_files(path):
    bin_files = list()
    extensions = ["000", "001", "002", "003", "004", "005", "BIN"]
    for extension in extensions:
        bin_files += glob.glob(path + "*." + extension)
    bin_files = [x.split("/")[-1] for x in bin_files]
    bin_files.sort()

    bin = b''
    for bin_file in bin_files:
        # If log extension is a digit, fill the log string
        if bin_file[-3:].isdigit():
            with open(path + bin_file, "rb") as fl:
                # We assume that files are sorted in a correct order
                bin += fl.read()
            os.remove(path + bin_file)
        else:
            if len(bin) > 0:
                # If log extension is not a digit and the log string is not empty
                # we need to add it at the end of the file
                with open(path + bin_file, "rb") as fl:
                    bin += fl.read()
                with open(path + bin_file, "wb") as fl:
                    fl.write(bin)
                bin = b''
# Decrypt one file with LOG, WARN,and ERR cards give in arguments
def decrypt_one(path,LOG_card,WARN_card,ERR_card,version):
    #parse data
    string =""
    with open(path, "rb") as f:
        byte = f.read(1)
        while byte != "":
            byte = f.read(1)
            if byte != b'#':
                continue
            else :
                byte = f.read(1)
                if byte != b'*':
                    continue
                else :
                    #Read head
                    IDbytes = f.read(2)
                    if len(IDbytes) != 2 :
                        print "err:IDbytes"
                        break;
                    TIMESTAMPbytes = f.read(4)
                    if len(TIMESTAMPbytes) != 4 :
                        print "err:TIMESTAMPbytes"
                        break;
                    INFOSbytes = f.read(1)
                    if INFOSbytes == "" :
                        print "err:INFOSbytes"
                        break;
                    DATASIZEbytes = f.read(1)
                    if DATASIZEbytes == "" :
                        print "err:DATASIZEbytes"
                        break;

                    #unpack head
                    try :
                        id = struct.unpack('<H', IDbytes)[0]
                        timestamp = struct.unpack('<I', TIMESTAMPbytes)[0]
                        infos = struct.unpack('<B', INFOSbytes)[0]
                        dataSize = struct.unpack('<B', DATASIZEbytes)[0]
                    except :
                        traceback.print_exc()

                    #Process head
                    idString = "0x"+"{0:0{1}X}".format(id,4)+"UL"
                    binaryinfo = "{0:08b}".format(infos)
                    type = "00"
                    argformat = "00"
                    type = binaryinfo[-2:]
                    argformat = binaryinfo[-4:-2]
                    if argformat != "00":
                        continue

                    #print "ID : " + str(id)
                    #print "IDString : " + str(idString)
                    #print "Timestamp : " + str(timestamp)
                    #print "Infos : " + str(infos)
                    #print "BinaryInfos : " + str(binaryinfo)
                    #print "Type : " + str(type)
                    #print "ArgFormat : " + str(argformat)
                    #print "dataSize : " + str(dataSize)


                    decrypt_card={}
                    type_string = ""
                    if type == "00":
                        decrypt_card = LOG_card
                    elif type == "01":
                        type_string = "<WARN>"
                        decrypt_card = WARN_card
                    elif type == "10":
                        type_string = "<ERR>"
                        decrypt_card = ERR_card
                    else :
                        type_string = "<DBG>"

                    Formats = []
                    File = "MAIN"
                    Level = "1"

                    if(id < len(decrypt_card)) :
                        index = id
                    else :
                        index = len(decrypt_card)-1

                    while index >= 0 :
                        if decrypt_card[index]["ID"] == idString:
                            Formats = decrypt_card[index]["FORMATS"]
                            File = decrypt_card[index]["FILE"]
                            Level = decrypt_card[index]["LEVEL"]
                            break;
                        index = index - 1

                    if int(Level) > user_level :
                        continue
                    if len(Formats) <= 0 :
                        f.read(dataSize)
                        string+=str(timestamp) + ":" + type_string + "["+"{:04d}".format(id)+"] Format not found\r\n"
                        continue
                    #print Formats
                    string += str(timestamp) + ":" + type_string
                    string +="["+"{:6}".format(File)+","+"{:04d}".format(id)+"]"
                    index=0
                    argIndex=0
                    if dataSize > 0:
                        while index < dataSize :
                            #Read Argument Head
                            ARGINFOSByte = f.read(1)
                            if ARGINFOSByte == "":
                                print "err:ARGINFOSByte"
                                break
                            ARGSIZEByte = f.read(1)
                            if ARGSIZEByte == "":
                                print "err:ARGSIZEByte"
                                break
                            #Unpack Argument Head
                            try :
                                ArgInfos=struct.unpack('<B', ARGINFOSByte)[0]
                                ArgSize = struct.unpack('<B', ARGSIZEByte)[0]
                            except :
                                traceback.print_exc()
                                print "err:INFOSSIZE"

                            #Process Argument Head
                            ArgInfosBinary="{0:08b}".format(ArgInfos)
                            ArgType = ArgInfosBinary[-2:]

                            #print "ArgInfosBinary : " + str(ArgInfosBinary)
                            #print "ArgType : " + str(ArgType)
                            #print "ArgSize : " + str(ArgSize)
                            index = index+2
                            Formats[argIndex] = Formats[argIndex].replace(r"\r\n","\r\n")
                            if ArgSize > 0:
                                Arg = 0
                                if ArgType == "00":
                                    # integer
                                    if ArgSize == 4:
                                        ArgByte = f.read(4)
                                        if len(ArgByte) != 4 :
                                            print "err:TYPE00SIZE04"
                                            break;
                                        try :
                                            Arg = struct.unpack('<i', ArgByte)[0]
                                        except :
                                            traceback.print_exc()
                                            print "err:TYPE00SIZE04"
                                    elif ArgSize == 2:
                                        ArgByte = f.read(2)
                                        if len(ArgByte) != 2 :
                                            print "err:TYPE00SIZE02"
                                            break;
                                        try :
                                            Arg = struct.unpack('<h', ArgByte)[0]
                                        except :
                                            traceback.print_exc()
                                            print "err:TYPE00SIZE02"
                                    elif ArgSize == 1:
                                        ArgByte = f.read(1)
                                        if ArgByte == "" :
                                            print "err:TYPE00SIZE01"
                                            break;
                                        try :
                                            Arg = struct.unpack('<b', ArgByte)[0]
                                        except :
                                            traceback.print_exc()
                                            print "err:TYPE00SIZE01"
                                elif ArgType == "01":
                                    # unsigned integer
                                    if ArgSize == 4:
                                        ArgByte = f.read(4)
                                        if len(ArgByte) != 4 :
                                            print "err:TYPE01SIZE04"
                                            break;
                                        try :
                                            Arg = struct.unpack('<I', ArgByte)[0]
                                        except :
                                            traceback.print_exc()
                                            print "err:TYPE01SIZE04"
                                    elif ArgSize == 2:
                                        ArgByte = f.read(2)
                                        if len(ArgByte) != 2 :
                                            print "err:TYPE01SIZE02"
                                            break;
                                        try :
                                            Arg = struct.unpack('<H', ArgByte)[0]
                                        except :
                                            traceback.print_exc()
                                            print "err:TYPE01SIZE02"
                                    elif ArgSize == 1:
                                        ArgByte = f.read(1)
                                        if ArgByte == "":
                                            print "err:TYPE01SIZE01"
                                            break
                                        try :
                                            Arg = struct.unpack('<B', ArgByte)[0]
                                        except :
                                            traceback.print_exc()
                                            print "err:TYPE01SIZE01"
                                elif ArgType == "11":
                                    # string
                                    ArgByte = f.read(ArgSize)
                                    if len(ArgByte) != ArgSize :
                                        print "err:TYPE11"
                                        break;
                                    try :
                                        Arg = struct.unpack("%ds" % ArgSize, ArgByte)[0]
                                    except :
                                        traceback.print_exc()
                                        print "err:TYPE11"
                                    if ord(Arg[ArgSize-1]) == 0 :
                                        Arg = Arg[:-1]
                                    #replace none ascii characters
                                    Arg = ''.join([i if ord(i) < 128 else ' ' for i in Arg])

                                #print ArgSize
                                #print Arg
                                #print "Format : " + str(Formats[argIndex]) + "\r\n"
                                try :
                                    if "%.*s" in Formats[argIndex]:
                                        string += Formats[argIndex] % (ArgSize,Arg)
                                    else :
                                        string += Formats[argIndex] % Arg
                                except :
                                    traceback.print_exc()
                                    print "error format"
                            else :
                                #print "Format : " + str(Formats[argIndex]) + "\r\n"
                                string += str(Formats[argIndex])
                                index = index + 1
                            index = index + ArgSize
                            argIndex = argIndex + 1
                    else :
                        #print "Format : " + (Formats[0].replace(r"\r\n","\r\n")) + "\r\n"
                        string += str(Formats[0].replace(r"\r\n","\r\n"))
                    string += "\r\n"
    #print "finished"
    return string
# Decrypt all BIN files in a path
def decrypt_all(path):
    # Generate List of BINS file
    #print path
    files_to_decrypt = glob.glob(path + "*.BIN")
    #print files_to_decrypt
    for file in files_to_decrypt :
        # Get version line
        print file
        with open(file, "r") as f:
            version = f.readline()
        # Get version
        catch = re.findall("<BDD ([0-9]{3})\.[0-9]{3}\.[0-9]{3}_?V?([0-9]*\.[0-9]+)-?.*>", version)
        #print catch
        if len(catch) > 0:
            # Get database file path
            absFilePath = os.path.abspath(__file__)
            scriptpath, scriptfilename = os.path.split(absFilePath)
            file_version=catch[-1][1].split(".")
            file_major = '2'
            file_minor = '17'

            if file_version[0] :
                file_major = file_version[0]
            if file_version[1] :
                file_minor = file_version[1]

            file_version = file_major+'.'+file_minor
            model = 0
            if catch[-1][0] == "589" :
                model = 1
            database_file = get_database_version(file_version,model)
            if database_file != "" :
                database_file_path = os.path.join(scriptpath,"databases",database_file)
                if os.path.exists(database_file_path):
                    # Read and Parse Database file
                    with open(database_file_path,"r") as f:
                        decryptlist = json.loads(f.read())
                    for decryptcard in decryptlist:
                        if decryptcard["TYPE"] == "LOG":
                            LOGcard = decryptcard["DECRYPTCARD"]
                        elif decryptcard["TYPE"] == "WARN":
                            WARNcard = decryptcard["DECRYPTCARD"]
                        elif decryptcard["TYPE"] == "ERR":
                            ERRcard = decryptcard["DECRYPTCARD"]
                    #print file
                    try :
                        Log_file = decrypt_one(file,LOGcard,WARNcard,ERRcard,file_version)
                    except:
                        traceback.print_exc()
                        print "FORMAT ERROR :" +str(file)
                    else:
                        with open(file.replace(".BIN",".LOG"),"w") as f:
                            f.write(Log_file)
                        print file.replace(".BIN",".LOG")
                else:
                    print "No database : " + str(database_file_path)

if __name__ == "__main__":
    decrypt_all("../server/osean/decrypt/bins/")
