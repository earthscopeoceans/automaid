import glob

 # Concatenate .000 files .LOG and .BIN files in the path
def concatenate_files(path):
    #LOG FILES
    log_files_path = glob.glob(path + "*.LOG")
    log_files_path_filtered = list()
    bin_files_path = glob.glob(path + "*.BIN")
    processed_path = list()

    for log_file_path in log_files_path:
        ok_file = True
        for bin_file_path in bin_files_path:
            if bin_file_path[:-4] == log_file_path[:-4]:
                ok_file = False
                break
        if ok_file :
            log_files_path_filtered.append(log_file_path)

    for log_file_path in log_files_path_filtered:
        logstring = ""
        files_to_merge = list(glob.glob(log_file_path[:-4] +".[0-9][0-9][0-9]"))
        files_to_merge.append(log_file_path)
        files_to_merge.sort()
        if len(files_to_merge) > 1:
            processed_path.append(log_file_path)
            for file_to_merge in files_to_merge :
                if file_to_merge[-3:].isdigit():
                    with open(file_to_merge, "r") as fl:
                        # We assume that files are sorted in a correct order
                        logstring += fl.read()
                else :
                    if len(logstring) > 0:
                        # If log extension is not a digit and the log string is not empty
                        # we need to add it at the end of the file
                        with open(file_to_merge, "r") as fl:
                            logstring += fl.read()
                        with open(file_to_merge, "w") as fl:
                            fl.write(logstring)
                        logstring = ""

    #BIN FILES
    for bin_file_path in bin_files_path:
        bin = b''
        files_to_merge = list(glob.glob(bin_file_path[:-4] +".[0-9][0-9][0-9]"))
        files_to_merge.append(bin_file_path)
        files_to_merge.sort()
        if len(files_to_merge) > 1:
            for file_to_merge in files_to_merge :
                if file_to_merge[-3:].isdigit():
                    with open(file_to_merge, "rb") as fl:
                        # We assume that files are sorted in a correct order
                        bin += fl.read()
                else :
                    if len(bin) > 0:
                        # If log extension is not a digit and the log string is not empty
                        # we need to add it at the end of the file
                        with open(file_to_merge, "rb") as fl:
                            bin += fl.read()
                        with open(file_to_merge, "wb") as fl:
                            fl.write(bin)
                        bin = b''
    return processed_path
