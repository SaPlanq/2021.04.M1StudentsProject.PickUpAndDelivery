import pathlib
import asyncio
import os
import json
from datetime import datetime

from parse import user_args, config_verif
from synchronize import Synchronize
from loader import compile_loader, load_data
from files import load_file, save_csv
from path_generation import path_generation
from path_optimization import path_optimization
from path_fusion import path_fusion
from common import print_generated, print_fusionned, format_csv
from graph import make_graph

from defines import ENGINE_FOLDER, TMP_FILE, RESULT_FOLDER, DASHBOAD_URL

if __name__ == "__main__":
    # step0 : compile numba functions, create dirs
    print(f"{datetime.now().time()} - Initializing...\n")
    compile_loader()
    path = str(pathlib.Path(__file__).parent.absolute())

    if not os.path.exists(path+RESULT_FOLDER):
        os.makedirs(path+RESULT_FOLDER)

    # step1.1 : get args, config, parse json config, get input data
    print(f"{datetime.now().time()} - Retrieve inputs...\n")
    config_name, online = user_args(path)

    if online:
        drive = Synchronize(path)
        config = drive.set_configfile(config_name).get_config()
    else:
        config = load_file(config_name)

    config = config_verif(path, json.loads(config))

    if online:
        datafile = drive.set_datafile(config["input_datafile"]).get_input()
    else:
        ext = "" if config["input_datafile"][-5:] == ".data" else ".data"
        datafile = load_file(path+"\\..\\"+config["input_datafile"] + ext)

    # step1.2 : parse input data, divide it : needed for computation and not
    print(f"{datetime.now().time()} - Parsing input...\n")
    local_data, to_compute = load_data(datafile)

    # step1.3 : generate input datafile
    # 5 first rules belongs to numpy array print
    data = str(to_compute).replace("\n", "") \
                          .replace("      ", "") \
                          .replace("array(", "") \
                          .replace(", dtype=float32)", "") \
                          .replace(",dtype=float32)", "") \
                          .replace("'", '"')
    file_path = path+ENGINE_FOLDER+TMP_FILE
    open(file_path, "w").write(data)

    # step2.1 : compute data
    print(f"{datetime.now().time()} - Simulate paths...\n")
    inputs = (config["path_generation"]["algorithm"],
              config["path_generation"]["nb_process"],
              file_path,
              list(config["results"]["KPI_weighting"].values()))
    results_gen = asyncio.run(path_generation(*inputs, to_compute))

    # step2.2 : optional print of results
    if config["results"]["print_console"]:
        print(f"{datetime.now().time()} - Display step1 results...\n")
        print_generated(local_data, results_gen,
                        list(config["results"]["KPI_weighting"].keys()))

    # # step3.1 : apply post processing
    # async run path_optimization()
    results_opti = [-1]*len(results_gen)
    # results_opti[2] = 1

    # # step3.2 : optional print of results
    # if config["results"]["print_console"]:
    #     print(f"{datetime.now().time()} - Display step2 results...\n")
    #     print_optimized(fusionned_path)

    # # step4.1 : collect data for path fusion
    # result_fusion = path_fusion(to_compute["arc"], results, config["path_fusion"]["algorithm"])

    # # step4.2 : optional print of results
    # if config["results"]["print_console"]:
    #     print(f"{datetime.now().time()} - Display step3 results...\n")
    #     print_fusionned(fusionned_path)

    # step5.1 : csv formatting and optional saving
    print(f"{datetime.now().time()} - Prepare CSV...\n")
    coords_csv, orders_csv, execution_csv = format_csv(local_data, to_compute, results_gen, results_opti)
    if config["results"]["keep_local"]:
        result_path = path+RESULT_FOLDER+"\\"+config['input_datafile']+"_{0}.csv"
        save_csv(result_path.format("coords"), coords_csv)
        save_csv(result_path.format("orders"), orders_csv)
        save_csv(result_path.format("executions"), execution_csv)

    # step5.2 : optional graph generation
    if config["results"]["graph"]["make"]:
        print(f"{datetime.now().time()} - Generate graphs...\n")
        inputs = (config["input_datafile"],
                  config["results"]["graph"]["show_names"],
                  config["results"]["graph"]["link_vertices"],
                  config["results"]["graph"]["map_background"],
                  config["results"]["graph"]["gif_mode"],
                  config["results"]["graph"]["fps"])
        files = make_graph(path, local_data, to_compute, results_gen, *inputs)

    # step6.1 : send results online
    if online:
        print(f"{datetime.now().time()} - Upload data...\n")
        if config["results"]["graph"]["make"]:
            drive.upload_imgs(config["results"]["graph"]["gif_mode"])
        drive.upload_csv(orders_csv, coords_csv, execution_csv, config["path_generation"]["nb_process"])

    # step6.2 : optional cleaning
    if config["results"]["graph"]["make"] and \
            not config["results"]["keep_local"]:
        print(f"{datetime.now().time()} - Clear directory...\n")
        [os.remove(file) for file in files if os.path.exists(file)]

    # step6.3 : finish
    print(f"{datetime.now().time()} - Everything done!\n")
    if online:
        print(f"Please consult results on dashboard :\n{DASHBOAD_URL}\n")
