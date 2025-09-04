import pickle
import gps

from obspy import UTCDateTime

def get_mermaid_cycles(mermaid_name):
    # Open database with position and events information
    pickle_path = "../data/processed/" + mermaid_name + "/" + mermaid_name + ".pickle"
    with open(pickle_path, "rb") as input_file:
        mermaid_cycles = pickle.load(input_file)
    return mermaid_cycles


def get_position(cycles, requested_date):
    position = None
    for cycle in sorted(cycles, key=lambda x: x.start_date):
        if cycle.descent_last_loc_before_event is not None and cycle.ascent_first_loc_after_event is not None:
            print(cycle.descent_last_loc_before_event.date)
            if cycle.descent_last_loc_before_event.date < requested_date < cycle.ascent_first_loc_after_event.date:
                position = gps.linear_interpolation([cycle.descent_last_loc_before_event,
                                                     cycle.ascent_first_loc_after_event], requested_date)
                break
    return position


if __name__ == "__main__":
    mermaid_name = "452.020-P-06"
    mermaid_cycles = get_mermaid_cycles(mermaid_name)

    requested_date = UTCDateTime(2018,9,1,0,0,0)
    requested_position = get_position(mermaid_cycles, requested_date)

    print("Position the " + str(requested_date) + " is " + str(requested_position.latitude) + " lat, " + str(requested_position.longitude) + " lon")
