# -*- coding: utf-8 -*-
# @Author: fro
# @Date:   2024-10-23 10:29:38
# @Last Modified by:   fro
# @Last Modified time: 2025-05-15 11:48:33
# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v3.10)
#
# Developer: Frédéric rocca <FRO>
# Contact:  frederic.rocca@osean.fr
# Last modified by FRO: 09-Sep-2024
# Last tested: Python 3.10.13, 22.04.3-Ubuntu



import glob
import os
import shutil
import json
import requests
import struct
import re
import traceback
import functools
import utils
from obspy import UTCDateTime

mermaid_path = os.environ["MERMAID"]
database_path = os.path.join(mermaid_path, "database")
DATABASE_LINK_NAME = "Databases.json"


def database_update(path):
    '''

    Update databases files into 'database_path' (need connection)
    (Does not stop script execution if connection is not established)

    Keyword arguments:
    path -- Path to store databases, can be null (defaut : os.environ["MERMAID"]/database)

    '''
    print("Update Databases")
    network = 1
    if path :
        global database_path
        database_path = path
    try:
        # Get linker file (link database and profiler version)
        url = 'http://mermaid.osean.fr/databases/' + DATABASE_LINK_NAME
        request = requests.get(url, auth=('osean', 'osean3324'), timeout=10)
    except Exception as e:
        print("Exception: \"" + str(e) + "\" detected when get " + DATABASE_LINK_NAME)
        network = 0
    else:
        if request.status_code == 200:
            # Read link file content into object
            database_list = request.json()
            # Retreive list of databases into linker file
            for database in database_list:
                if database["Name"]:
                    try:
                        # Get Database files (one by one)
                        url_database = 'http://mermaid.osean.fr/databases/' + database["Name"]
                        new_req = requests.get(url_database, auth=('osean', 'osean3324'), timeout=10)
                        # Store temporary database into linker object
                        database["data"] = new_req.json()
                        if new_req.status_code != 200:
                            print("Error " + str(new_req.status_code) + " when get " + database["Name"])
                            network = 0
                    except Exception as e:
                        print("Exception: \"" + str(e) + "\" detected when get " + str(database["Name"]))
                        network = 0
        else:
            print("Error " + str(request.status_code) + " when get " + DATABASE_LINK_NAME)
            network = 0
        if network > 0:
            # All databases received correctly => delete current files
            if os.path.exists(database_path):
                shutil.rmtree(database_path)
            os.makedirs(database_path)
            # Store databases content
            for database in database_list:
                if database["Name"]:
                    path = os.path.join(database_path, database["Name"])
                    with open(path, 'w') as databasefile:
                        json.dump(database["data"], databasefile)
                    # Delete content from link object
                    database.pop('data', None)
            # Store link file
            link_path = os.path.join(database_path, DATABASE_LINK_NAME)
            with open(link_path, 'w') as linkfile:
                json.dump(database_list, linkfile, indent=4)


'''

Concatenate files with decimal extensions
.000 .001 .002 .LOG => .LOG
.000 .001 .002 .BIN => .BIN

Keyword arguments:
path -- Path with source files of one profiler

'''
 # Concatenate .[0-9][0-9][0-9] files .LOG and .BIN files in the path
def concatenate_files(path):
    # List log files (not cyphered)
    files_path = glob.glob(path + "*.LOG")
    # Add bin files
    files_path += glob.glob(path + "*.BIN")
    # Concatenate all files
    for file_path in files_path:
        bin = b''
        # list file with same head than log file
        files_to_merge = list(glob.glob(file_path[:-4] +".[0-9][0-9][0-9]"))
        # Add end file to the list
        files_to_merge.append(file_path)
        # Sort list => [0000_XXXXXX.000,0000_XXXXXX.001,0000_XXXXXX.002,0000_XXXXXX.LOG]
        files_to_merge.sort()
        if len(files_to_merge) > 1:
            # Need to merge multiple file
            for file_to_merge in files_to_merge :
                if file_to_merge[-3:].isdigit():
                    # Extension with digit => append to string
                    with open(file_to_merge, "rb") as fl:
                        bin += fl.read()
                    # Remove file after read
                    os.remove(file_to_merge)
                else :
                    if len(bin) > 0:
                        # If log extension is not a digit and the log string is not empty
                        # we need to add it at the end of the file
                        with open(file_to_merge, "rb") as fl:
                            bin += fl.read()
                        with open(file_to_merge, "wb") as fl:
                            fl.write(bin)
                        bin = b''

'''

Concatenate RBR files with decimal extensions
.RBR .RB0 .RB1 .RB3 => .RBR

Keyword arguments:
path -- Path with source files of one profiler

'''
def concatenate_rbr_files(path):
    files_path = glob.glob(path + "*.RBR")
    for file_path in files_path:
        # list file with same head than log file
        files_to_merge = list(glob.glob(file_path[:-4] +".R[0-9][0-9]"))
        # Sort list => [0000_XXXXXX.R00,0000_XXXXXX.R01,0000_XXXXXX.R02,0000_XXXXXX.R03]
        files_to_merge.sort()       
        for file_to_merge in files_to_merge :
            bin = b''
            with open(file_to_merge, "rb") as fl:
                bin = fl.read()
            with open(file_path, "ab") as fl:
                fl.write(bin)
                # Remove file after append
                os.remove(file_to_merge)

# Get database name with linker file and version read on file
'''

Read link file and return the database associated with the binary file.

Keyword arguments:
file_version -- String contain version of profiler with format MAJOR.MINOR
model -- Model number of the profiler (0:classic;1:Marittimo(Moored version);2:Multimer(Next generation))

'''
def decrypt_get_database(file_version,model) :
    link_path = os.path.join(database_path,DATABASE_LINK_NAME)
    if os.path.exists(link_path):
        with open(link_path,"r") as f:
            databases = json.loads(f.read())
        # get major and minor versions
        file_version=file_version.split(".")
        file_major = 2
        file_minor = 17
        if file_version[0] :
            file_major = int(file_version[0])
        if file_version[1] :
            file_minor = int(file_version[1])
        # force model when version is superior to 2
        if file_major > 2 :
            model = 3

        for database in databases :
            if model == database["Model"]:
                database_minor_max = 2147483647
                database_major_max = 2147483647
                databaseMin_version = database["MinVersion"].split(".")
                database_major_min = int(databaseMin_version[0])
                database_minor_min = int(databaseMin_version[1])
                if database["MaxVersion"] != "None":
                    databaseMax_version = database["MaxVersion"].split(".")
                    database_major_max = int(databaseMax_version[0])
                    database_minor_max = int(databaseMax_version[1])
                if ((file_major > database_major_min) and (file_minor < database_minor_max)) \
                or ((file_major >= database_major_min) and (file_major <= database_major_max) \
                and (file_minor >= database_minor_min) and (file_minor <= database_minor_max)) :
                    print("Database name : " + database["Name"])
                    return database["Name"]
                #print "\r\n"
        print(("No Database available for : " + str(file_version)))
        return ""
    else :
        print(("No link file : " + link_path))
        return ""



'''

Decrypts a log line using an expilicit format
The number and size of arguments is explicitly described in the binary file.

Keyword arguments:
f -- file reader
LOG_card -- Object for LOG decryption (database)
WARN_card -- Object for WARNING decryption (database)
ERR_card -- Object for ERROR decryption (database)

'''

def decrypt_explicit(f,LOG_card,WARN_card,ERR_card) :
    #Read head
    string = ""
    IDbytes = f.read(2)
    if len(IDbytes) != 2 :
        print("err:IDbytes")
        return "";
    TIMESTAMPbytes = f.read(4)
    if len(TIMESTAMPbytes) != 4 :
        print("err:TIMESTAMPbytes")
        return "";
    INFOSbytes = f.read(1)
    if INFOSbytes == "" :
        print("err:INFOSbytes")
        return "";
    DATASIZEbytes = f.read(1)
    if DATASIZEbytes == "" :
        print("err:DATASIZEbytes")
        return "";
    #unpack head
    try :
        id = struct.unpack('<H', IDbytes)[0]
        timestamp = struct.unpack('<I', TIMESTAMPbytes)[0]
        infos = struct.unpack('<B', INFOSbytes)[0]
        dataSize = struct.unpack('<B', DATASIZEbytes)[0]
    except :
        traceback.print_exc()
        print("err:header")
        return "";

    #Process head
    idString = "0x"+"{0:0{1}X}".format(id,4)+"UL"
    binaryinfo = "{0:08b}".format(infos)
    logtype = "00"
    argformat = "00"
    logtype = binaryinfo[-2:]
    argformat = binaryinfo[-4:-2]
    if argformat != "00":
        return "";

    #print ("ID : " + str(id))
    #print ("IDString : " + str(idString))
    #print ("Timestamp : " + str(timestamp))
    #print ("Infos : " + str(infos))
    #print ("BinaryInfos : " + str(binaryinfo))
    #print ("Type : " + str(type))
    #print ("ArgFormat : " + str(argformat))
    #print ("dataSize : " + str(dataSize))

    decrypt_card={}
    type_string = ""
    if logtype == "00":
        decrypt_card = LOG_card
    elif logtype == "01":
        type_string = "<WARN>"
        decrypt_card = WARN_card
    elif logtype == "10":
        type_string = "<ERR>"
        decrypt_card = ERR_card
    else :
        type_string = "<DBG>"

    Formats = []
    File = "MAIN"

    if(id < len(decrypt_card)) :
        index = id
    else :
        index = len(decrypt_card)-1
    while index >= 0 :
        if decrypt_card[index]["ID"] == idString:
            Formats = decrypt_card[index]["FORMATS"]
            File = decrypt_card[index]["FILE"]
            break;
        index = index - 1

    if len(Formats) <= 0 :
        f.read(dataSize)
        string += str(timestamp) + ":" + type_string + "["+"{:04d}".format(id)+"] Format not found\r\n"
        return string
    #print (Formats)
    if File != "__BLANK__" :
        string += str(timestamp) + ":"
        string +="["+"{:6}".format(File)+","+"{:04d}".format(id)+"]"
        string += type_string
    index=0
    argIndex=0
    if dataSize > 0:
        while index < dataSize :
            #Read Argument Head
            ARGINFOSByte = f.read(1)
            if ARGINFOSByte == "":
                print("err:ARGINFOSByte")
                return "";
            ARGSIZEByte = f.read(1)
            if ARGSIZEByte == "":
                print("err:ARGSIZEByte")
                return "";
            #Unpack Argument Head
            try :
                ArgInfos=struct.unpack('<B', ARGINFOSByte)[0]
                ArgSize = struct.unpack('<B', ARGSIZEByte)[0]
            except :
                traceback.print_exc()
                print("err:INFOSSIZE")
                return "";

            #Process Argument Head
            ArgInfosBinary="{0:08b}".format(ArgInfos)
            ArgType = ArgInfosBinary[-2:]

            #print ("ArgInfosBinary : " + str(ArgInfosBinary))
            #print ("ArgType : " + str(ArgType))
            #print ("ArgSize : " + str(ArgSize))
            index = index+2
            Formats[argIndex] = Formats[argIndex].replace(r"\r\n","\r\n")
            if ArgSize > 0:
                Arg = 0
                if ArgType == "00":
                    if ArgSize == 4:
                        ArgByte = f.read(4)
                        if len(ArgByte) != 4 :
                            print("err:TYPE00SIZE04")
                            return "";
                        try :
                            Arg = struct.unpack('<i', ArgByte)[0]
                        except :
                            traceback.print_exc()
                            print("err:TYPE00SIZE04")
                            return "";
                    elif ArgSize == 2:
                        ArgByte = f.read(2)
                        if len(ArgByte) != 2 :
                            print("err:TYPE00SIZE02")
                            return "";
                        try :
                            Arg = struct.unpack('<h', ArgByte)[0]
                        except :
                            traceback.print_exc()
                            print("err:TYPE00SIZE02")
                            return "";
                    elif ArgSize == 1:
                        ArgByte = f.read(1)
                        if ArgByte == "" :
                            print("err:TYPE00SIZE01")
                            return "";
                        try :
                            Arg = struct.unpack('<b', ArgByte)[0]
                        except :
                            traceback.print_exc()
                            print("err:TYPE00SIZE01")
                            return "";
                elif ArgType == "01":
                    # unsigned integer
                    if ArgSize == 4:
                        ArgByte = f.read(4)
                        if len(ArgByte) != 4 :
                            print("err:TYPE01SIZE04")
                            return "";
                        try :
                            Arg = struct.unpack('<I', ArgByte)[0]
                        except :
                            traceback.print_exc()
                            print("err:TYPE01SIZE04")
                            return "";
                    elif ArgSize == 2:
                        ArgByte = f.read(2)
                        if len(ArgByte) != 2 :
                            print("err:TYPE01SIZE02")
                            return "";
                        try :
                            Arg = struct.unpack('<H', ArgByte)[0]
                        except :
                            traceback.print_exc()
                            print("err:TYPE01SIZE02")
                            return "";
                    elif ArgSize == 1:
                        ArgByte = f.read(1)
                        if ArgByte == "":
                            print("err:TYPE01SIZE01")
                            return "";
                        try :
                            Arg = struct.unpack('<B', ArgByte)[0]
                        except :
                            traceback.print_exc()
                            print("err:TYPE01SIZE01")
                            return "";
                elif ArgType == "11":
                    # string
                    ArgByte = f.read(ArgSize)
                    if len(ArgByte) != ArgSize :
                        print("err:TYPE11")
                        return "";
                    if ArgByte[ArgSize-1] == 0 :
                        ArgByte = ArgByte[:-1]
                    Arg = ArgByte
                    try :
                        Arg = Arg.decode('ascii', 'ignore')
                    except :
                        traceback.print_exc()
                        print("err:TYPE11")
                        return "";
                    #replace none ascii characters
                #print (ArgSize)
                #print ("Format : " + str(Formats[argIndex]) + "\r\n")
                try :
                    if "%c" in Formats[argIndex]:
                        if Arg < 0 :
                            Arg = 0
                        elif Arg > 0x10FFFF:
                            Arg = 0x10FFFF

                    if "%.*s" in Formats[argIndex]:
                        string += (Formats[argIndex] % (ArgSize,Arg))
                    else :
                        string += (Formats[argIndex] % Arg)
                except :
                    traceback.print_exc()
                    print("error format \"{}\" ARG {}".format(Formats[argIndex],Arg))
                    return "";
            else :
                #print ("Format : " + str(Formats[argIndex]) + "\r\n")
                string += str(Formats[argIndex])
                index = index + 1
            index = index + ArgSize
            argIndex = argIndex + 1
    else :
        #print ("Format : " + (Formats[0].replace(r"\r\n","\r\n")) + "\r\n")
        string += str(Formats[0].replace(r"\r\n","\r\n"))
    string += "\r\n"
    return string

def decrypt_short(f,short_card) :
    '''

    Decrypts a log line using an short format
    The number and size of arguments is implicit.
    Only frequently recurring logs use this format.
    (Pressure measurement, Pump time, valve time ...)

    Keyword arguments:
    f -- file reader

    '''
    string = ""
    id = f.read(1)
    format = ""
    shortId = 256
    if id == "" :
        print("err:EMPTYSHORTID")
        return "";
    try :
        shortId = struct.unpack('<B', id)[0]
    except :
        traceback.print_exc()
        print("err:UNPACKSHORTID")
        return "";

    # Search formats link to short log
    args = []
    if(shortId < len(short_card)) :
        index = shortId
    else :
        index = len(short_card)-1
    while index >= 0 :
        if short_card[index]["ID"] == shortId:
            args = short_card[index]["ARGS"]
            break;
        index = index - 1
    if len(args) == 0 :
        print("err:NoShortFormatFound")
        return ""

    # Get timestamp
    timestamp_bytes = f.read(4)
    if len(timestamp_bytes) != 4 :
        print("err:timestamp")
        return ""; 
    try :
        timestamp = struct.unpack('<I', timestamp_bytes)[0]     
    except :
        traceback.print_exc()    
        print("err:unpacktimestamp")
        return ""
    # Init format with timestamp
    format_str = str(timestamp) + ":"   
    for arg in args:
        size = arg["SIZE"]
        value = f.read(size)
        if len(value) != size :
            print("err:valueSize")
            return ""
        unpack_arg = ""
        # get format of value
        if arg["SIGN"] == "signed":
            if size == 4:
                unpack_arg = '<i'
            elif size == 2:
                unpack_arg = '<h'
            elif size == 1:
                unpack_arg = '<b'
            else :
                print("err:wrongsignedformat")
        elif arg["SIGN"] == "unsigned":
            if size == 4:
                unpack_arg = '<I'
            elif size == 2:
                unpack_arg = '<H'
            elif size == 1:
                unpack_arg = '<B'
            else :
                print("err:wrongunsignedformat")
        else :
            format_str = format_str + arg["FORMAT"]
            continue
        # unpack argument value
        try :
            arg_value = struct.unpack(unpack_arg, value)[0]
        except :
            traceback.print_exc()    
            print("err:unpackvalue")
            return ""   
        # seach specific format
        regexShortFomat = "[^%]*(%([\-\+ 0])?(\d)*\.?([\d\*])*([dfcsXxupt]))"
        shortformatfind = re.findall(regexShortFomat, arg["FORMAT"])
        if len(shortformatfind) == 0 :
            print("err:wrongformat")
            return ""

        replace_pattern = shortformatfind[0][0]
        flags = shortformatfind[0][1]
        width = shortformatfind[0][2]
        precision = shortformatfind[0][3]
        specifier = shortformatfind[0][4]
        if specifier == 't' :
            # value is a timestamp
            isodate = UTCDateTime(int(arg_value)).isoformat()
            isodate.replace(":","_")
            format_str = format_str + arg["FORMAT"].replace(replace_pattern,isodate)
        elif specifier == 'f' :
            # value is a float stored on integer
            divisor = 1
            if precision.isnumeric():
                divisor = 10 ** int(precision)
            argf = float(arg_value) / divisor
            argf_format = "{:." + precision + "f}"
            argf_str = argf_format.format(argf)
            format_str = format_str + arg["FORMAT"].replace(replace_pattern,argf_str)
        else :
            format_str = format_str + arg["FORMAT"] % arg_value
    return format_str + "\r\n"       


# Decrypt one file with LOG, WARN,and ERR cards give in arguments
def decrypt_one(path,LOG_card,WARN_card,ERR_card,short_card):
    '''

    Read a file byte by byte and wait for header characters.
    Depending on the header, we decrypt an explicit (decrypt_explicit) or implicit log (decrypt_short).

    Keyword arguments:
    f -- file reader
    LOG_card -- Object for LOG decryption (database)
    WARN_card -- Object for WARNING decryption (database)
    ERR_card -- Object for ERROR decryption (database)

    '''
    #parse data
    string =""
    with open(path, "rb") as f:
        byte = f.read(1)
        while byte != b'':
            byte = f.read(1)
            if byte != b'#':
                if byte != b'@':
                    continue
                else :
                    string += decrypt_short(f,short_card);
            else :
                byte = f.read(1)
                if byte != b'*':
                    continue
                else :
                    string += decrypt_explicit(f,LOG_card,WARN_card,ERR_card);
    return string


# Decrypt all BIN files in a path
def decrypt_all(path):
    '''
    Decrypt all Binary file within a folder.
    1/ Read profiler software version and model number
    2/ Get database file
    3/ Read byte by byte file and decrypt it into .LOG file
    4/ Delete binary file

    Keyword arguments:
    path -- folder path

    '''
    # Generate List of BINS file
    files_to_decrypt = glob.glob(path + "*.BIN")
    files_decrypted = list()
    for binary_file in files_to_decrypt :
        # Get version line
        with open(binary_file, "r", errors='replace') as f:
            version = f.readline()
        # Get version
        catch = re.findall("<BDD ([0-9]{3})\.[0-9]{3}\.[0-9]{3}_?V?([0-9]*\.[0-9]+)-?.*>", version)
        if len(catch) > 0:
            # Get database binary_file path
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
            elif catch[-1][0] == "458" :
                model = 2

            database_file = decrypt_get_database(file_version,model)
            if database_file != "" :
                database_file_path = os.path.join(database_path,database_file)
                if os.path.exists(database_file_path):
                    # Read and Parse Database binary_file
                    database =""
                    with open(database_file_path,"r") as f:
                        database = f.read()
                    bin = b''
                    with open(binary_file,"rb") as bin_file:
                        bin = bin_file.read()

                    log_file = binary_file.replace(".BIN",".LOG")
                    binary_file_name = os.path.basename(binary_file)
                    log_file_name = binary_file_name.replace(".BIN",".LOG")

                    print("convert " + binary_file_name + " to " + log_file_name)
                    decrypt_list = json.loads(database)
                    for decrypt_card in decrypt_list:
                        if decrypt_card["TYPE"] == "LOG":
                            log_card = decrypt_card["DECRYPTCARD"]
                        elif decrypt_card["TYPE"] == "WARN":
                            warn_card = decrypt_card["DECRYPTCARD"]
                        elif decrypt_card["TYPE"] == "ERR":
                            err_card = decrypt_card["DECRYPTCARD"]
                        elif decrypt_card["TYPE"] == "SHORT":
                            short_card = decrypt_card["DECRYPTCARD"]
                    try :
                        result = decrypt_one(binary_file,log_card,warn_card,err_card,short_card)
                    except:
                        print(("FORMAT ERROR :" +str(binary_file)))
                        traceback.print_exc()
                    else:
                        if result :
                            with open(log_file,"w") as f:
                                f.write(result)
                            files_decrypted.append(log_file)
                        os.remove(binary_file)
                else:
                    print(("No database : " + str(database_file_path)))
    return files_decrypted


def get_hexa_date(filepath) :
    '''
    Get start date of a file with filepath (hexa format : <NUMB>_<HEXADATE>.<EXT>)
    <NUMB> : Buoy number (2 or 4 digits)
    <HEXADATE> : Number of seconds from epoch date (January 1st, 1970 at UTC) in hexadecimal format
    <EXT> : File extension

    Keyword arguments:
    filepath -- path of a .LOG .MER .BIN file

    '''
    return os.path.splitext(os.path.basename(filepath))[0].split("_")[1]


def sort_log_files(a,b):
    '''
    Sort a list of file in function of buoy_nb and start date (hexa format : <NUMB>_<HEXADATE>.<EXT>)
    <NUMB> : Buoy number (2 or 4 digits)
    <HEXADATE> : Number of seconds from epoch date (January 1st, 1970 at UTC) in hexadecimal format
    <EXT> : File extension

    Keyword arguments:
    a -- First file path to compare
    b -- Second file path to compare
    '''
    buoy_nbA = os.path.splitext(os.path.basename(a))[0].split("_")[0]
    buoy_nbB = os.path.splitext(os.path.basename(b))[0].split("_")[0]
    nbA = int(buoy_nbA,10)
    nbB = int(buoy_nbB,10)
    if nbA != nbB :
        return nbA - nbB
    else :
        baseA = get_hexa_date(a)
        baseB = get_hexa_date(b)
        timestampA = int(baseA,16)
        timestampB = int(baseB,16)
        return timestampA - timestampB



def convert_in_cycle(path,begin,end):
    '''
    Convert all *.LOG files into .CYCLE (LOG >= begin and LOG < end)
    1/ Merge all initialization files before first complete dive (cycle 0)
    2/ Fixes potential datation errors (e.g., 25_643FB6EF.LOG)
    3/ A complete cycle includes :
        - A complete log with one dive and one ascent
        - The list of GPS fixes following the dive
        - The list of log files in the CYCLE file
    4/ A cycle file will be named :
        <CYCLE_NB>_<HEXADATE>.CYCLE

    <CYCLE_NB> : CYCLE NUMBER (0:initialization 1:First dive...)
    <HEXADATE> : Date of file start / Number of seconds from epoch date (January 1st, 1970 at UTC) in hexadecimal format

    Keyword arguments:
    path -- process path
    begin -- UTCDateTime() object
    end -- UTCDateTime() object

    '''
    # Init cycle nb
    cycle_nb = 0
    # List all LOG files
    logFiles = glob.glob(os.path.join(path,"*.LOG"));
    # Sort files by names
    logFiles = sorted(logFiles, key=functools.cmp_to_key(sort_log_files))
    # Init Log index
    iLog = 0
    # Init Content of cycle file
    content = ""
    # Init file name and path variables
    cycle_file_name = None
    cycle_file_path = None
    # Split the path
    # Set default delimiter
    delim = "\r\n"

    while iLog < len(logFiles):
        # Get filepath
        logFile = logFiles[iLog]
        # Get file start date
        start_date = utils.get_date_from_file_name(os.path.basename(logFile))
        # File has been done during buoy lifetime ?
        if start_date >= begin and start_date < end :
            # Init cycle path and cycle name with first file created during lifetime
            if not cycle_file_name :
                cycle_file_name = "{:04d}".format(0) + "_" + get_hexa_date(logFile)
                cycle_file_path = os.path.join(path,cycle_file_name)
            # Init last date
            last_date = start_date
            with open(logFile, "rb") as f:
                # Read the content of the LOG
                fileRead = f.read().decode("utf-8","replace")
                if not fileRead :
                    iLog = iLog +1
                    continue
                fileFixed = ""
                # Get current delimiter char
                delim = utils.get_log_delimiter(fileRead)
                if not delim:
                    delim = "\r\n"
                if delim == "\r\n":
                   fileRead = fileRead.replace("\r\n","\n")
                   fileRead = fileRead.replace("\r","\n")
                   delim = "\n"
                #Split file by line
                is_dive = False
                is_finish = False
                is_gps_fix = False
                gps_fix_none = 0
                is_emergency = False
                is_reboot_in_dive = False
                lines = utils.split_log_lines(fileRead)
                for line in lines:
                    # Is diving ?
                    if not is_dive and re.findall("\[DIVING, *\d+\] *(\d+)mbar reached", line) :
                        is_dive = True
                    # File is switched ?
                    if not is_finish and re.findall("\*\*\* switching to.*", line) :
                        is_finish = True
                    # Gps fix ?
                    if not is_gps_fix and re.findall("GPS fix\.\.\.", line) :
                        is_gps_fix = True

                    # No GPS without gps fix date ?
                    gps_none_line = re.findall("(\d+):\[.+\]<WARN>no fix after",line)
                    if gps_none_line:
                        if not is_gps_fix :
                            last_datetime = str(int(gps_none_line[0]) - 180)
                            fileFixed += last_datetime + ":[SURF  ,0022]GPS fix..." + delim
                            gps_fix_none = 1
                            is_gps_fix = True
                        else :
                            gps_fix_none = gps_fix_none + 1
                            if gps_fix_none >= 3 :
                                is_gps_fix = False
                                gps_fix_none = 0

                    # GPS ACK without gps fix date ?
                    gps_ack_line = re.findall("\$GPSACK:.+;",line)
                    if gps_ack_line and not is_gps_fix:
                        last_datetime = str(int(last_date.timestamp))
                        fileFixed += last_datetime + ":[SURF  ,0022]GPS fix..." + delim
                        is_gps_fix = True
                    # GPS line without gps fix date ?
                    gps_line = re.findall("(\d+):\[SURF *, *\d+\]([S,N])(\d+)deg(\d+.\d+)mn", line)
                    if gps_line :
                        if not is_gps_fix :
                            last_datetime = str(int(last_date.timestamp))
                            fileFixed += last_datetime + ":[SURF  ,0022]GPS fix..." + delim
                        is_gps_fix = False
                    # Split line and test
                    catch = re.findall("(\d+):", line)
                    if len(catch) > 0:
                        datetime = UTCDateTime(int(catch[0]))
                        if datetime < start_date :
                            # line timestamp is before the start date ?
                            # Replace timestamp by last line timestamp or start date by default
                            # e.g., 25_643FB6EF.LOG
                            last_datetime = str(int(last_date.timestamp))
                            line.replace(catch[0],last_datetime)
                        last_date = datetime
                    # Append line into a string with time fixed
                    fileFixed += line + delim
                # Complete dive ?
                is_complete_dive = False
                if is_dive and is_finish :
                    is_complete_dive = True
                elif is_dive :
                    is_reboot_in_dive = True
                    print("{} reboot !!!!!!".format(os.path.basename(logFile)))

                # Test if the buoy has dived and surfaced or If the ascent is in the following files
                if is_complete_dive or is_reboot_in_dive :
                    # Split content to get before diving (First internal pressure mesurement)
                    content += str(int(get_hexa_date(logFile),16)) + ":[PREPROCESS]Create " + os.path.basename(logFile) + delim
                    lines = utils.split_log_lines(fileFixed)
                    before_dive = None
                    for index, line in enumerate(lines):
                        # Wait an internal pressure follower by bypass configuration
                        internal_pressure = re.findall('(\d+):.+internal pressure (-?\d+)Pa', line)
                        if internal_pressure :
                            next_index = index
                            while next_index < len(lines) - 1:
                                next_index = next_index+1
                                before_dive = re.findall('(\d+):(\[.+\])? +bypass (\d+)ms (\d+)ms \((\d+)ms (\d+)ms stored\)', lines[next_index])
                                if before_dive :
                                    break;
                            
                        # Wait start of next dive
                        if before_dive :
                            # exit the loop
                            content += before_dive[0][0] + ":[PREPROCESS]End of cycle" + delim
                            # Write a complete cycle
                            with open(cycle_file_path + ".CYCLE", "w") as fcycle:
                                fcycle.write(content)
                            # Increment cycle nb and change file name
                            cycle_nb = cycle_nb + 1
                            cycle_file_name = "{:04d}".format(cycle_nb) + "_" + get_hexa_date(logFile)
                            cycle_file_path = os.path.join(path,cycle_file_name)
                            # Reset content with current file (for next cycle)
                            content = ""
                            break
                        content += line + delim
                # Append filename
                content += str(int(get_hexa_date(logFile),16)) + ":[PREPROCESS]Create " + os.path.basename(logFile) + delim
                # Append file content
                content += fileFixed
        # Next File
        iLog = iLog +1
        #os.remove(logFile)

    # Write last incomplete cycle
    if content :
        with open(cycle_file_path + ".CYCLE", "w") as fcycle:
            fcycle.write(content)
