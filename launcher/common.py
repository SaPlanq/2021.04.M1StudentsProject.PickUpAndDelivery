from subprocess import Popen, PIPE
import asyncio
import time
import math
import os

from defines import TMP_FILE


async def execute_heuristic(data, batch_size, nb_process, exe_path):
    nb_trav = len(data["traveler"])
    current_pid = os.getpid()
    # 5 first rules belongs to numpy array print
    data = str(data).replace("\n", "") \
                    .replace("      ", "") \
                    .replace("array(", "") \
                    .replace(", dtype=float32)", "") \
                    .replace(",dtype=float32)", "") \
                    .replace("'", '"')
    file_path = exe_path[:exe_path.rfind("\\")]+TMP_FILE
    with open(file_path, "w") as file:
        file.write(data)
    batch_size = str(batch_size)
    running_procs = [Popen([exe_path, file_path, str(current_pid+id), batch_size],
                     stdout=PIPE, stderr=PIPE, text=True)
                     for id in range(nb_process)]

    results = []
    time1 = time.time()
    while running_procs:
        for proc in running_procs:
            retcode = proc.poll()  # check if available
            if not retcode:  # Process finished.
                running_procs.remove(proc)
                break

            else:  # No process is done, wait a bit and check again.
                await asyncio.sleep(.4)
                continue

        lines = proc.communicate()[0].split("\n")
        if retcode and retcode != 0:  # execution error
            print(f"process {current_pid - int(lines[0])} return error '{retcode}'")
            print(lines[1:])
            continue

        seed = lines[1]
        data = [line[:-1] for line in lines[2:2+nb_trav]]

        # preprocess results rather than sleep
        results = make_unique(seed, data, results)

    time2 = time.time()
    print(f'heuristics executions took {(time2-time1)*1000.0:.3f} ms\n')

    return format_result(results)  # sorted(format_result(results), key=lambda x: x[0])


def make_unique(seed, data, current):
    seed = int(seed)
    dist = []
    path = []
    for line in data:
        line = line.split(";")
        dist.append(float(line[0]))  # 0 if not used
        path.append(line[1])  # -1 if not used

    # generate match list
    duplicate = [id for id, couple in enumerate(current) if seed == couple[0]]

    # no match
    if not duplicate:
        current.append((seed, list(zip(dist, path))))

    # else : same random = same path = ignored

    return current


def make_unique_old(seed, data, current):
    dist, path = data.split(";")
    dist = float(dist)
    seed = int(seed)

    # generate match list
    comparing_all = [(path in f"{x[1]},{x[1]}" or path in f"{x[1]},{x[1]}"[::-1]) for x in current]

    # no match
    if len(comparing_all) == 0 or not comparing_all.__contains__(True):
        current.append((dist, path, seed))

    else:  # match: replace if shorter
        index = comparing_all.index(True)
        if current[index][0] > dist:
            current[index] = (dist, path, seed)

    return current


def format_result(data):
    for id_line, (_, line) in enumerate(data):
        for id_tuple, (dist, path) in enumerate(line):
            data[id_line][1][id_tuple] = (dist, [int(x) for x in path.split(",")])

    return data


def print_results(local_data, results):
    # greater nbs of digits
    max_digits_dist = 1+int(math.log10(int(results[-1][1][0][0])))
    max_digits_seed = 1+int(math.log10(max([x[0] for x in results])))

    print(f"{len(results)} distinc(s) peaks travel(s) order(s) :")

    for seed, travel_list in results:
        print(f"- seed {seed:{max_digits_seed}d} :")

        for id, (dist, travel) in enumerate(travel_list):
            travel = str([local_data["peak"][x]["name"] for x in travel])[1:-1]

            a = local_data['traveler'][id]['name']
            b = f"{dist:{max_digits_dist+3}.2f}"  # +3 => '.xx'
            c = "with "+travel.replace("', '", " -> ") if dist != 0 else ""
            print(f"\t{a} : {b}km {c}")

        print()


def format_csv(local_data, results):
    path_data = [["id", "total_distance", "path", "seed", "img"]]

    for id, res in enumerate(results):
        line = [str(id), f"'{res[0]}", "'"+local_data['peak'][res[1][0]]['name']]

        for peak in res[1][1:]:
            line[2] += f";{local_data['peak'][peak]['name']}"

        line[2] += "'"
        line.append(str(res[2]))

        path_data.append(line)

    cities_data = [["city_name", "lat", "long"]]

    for res in local_data["peak"]:
        cities_data.append([res['name'], str(res['y']), str(res['x'])])

    return path_data, cities_data


def save_csv(path, data):
    with open(path, "w") as file:
        for line in data:
            file.write(",".join(line)+"\n")
