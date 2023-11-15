from credentials_postgres_db import DBNAME, TABLE_NAME, HOST, PORT, USER, PASSWORD

from paramiko import SSHClient, AutoAddPolicy
from psycopg2 import connect, sql

from datetime import datetime
from pathlib import Path


def get_list_machines_to_scan_from_txt(filename: str) -> list:
    f = open(filename)
    machines_to_scan = f.readlines()
    f.close()
    return machines_to_scan


def get_main_os_info(ssh_client: SSHClient, host: str) -> dict:
    dict_main_info_os = {"host": host}
    logs = ""
    list_of_commands = ("cat /etc/os-release", "arch", "hostnamectl")

    for i in range(len(list_of_commands)):
        stdin, stdout, stderr = ssh_client.exec_command(list_of_commands[i])  # Выполняем команду
        stdout, stderr = stdout.read().decode(), stderr.read().decode()
        if stderr is not None:
            # В случае ошибки - беру только 1 строку описания ошибки, чтобы не захламлять файл с логами
            stderr = stderr.split("\n")[0]
        logs += f"{str(datetime.now().time().strftime('%H:%M:%S'))} - {host} - {list_of_commands[i]} {stderr}\n"
        structured_data = structurize_data(stdout, i)
        for key in structured_data.keys():
            if dict_main_info_os.get(key) is None:
                dict_main_info_os[key] = structured_data[key]

    write_logs_to_file(logs)
    return dict_main_info_os


def structurize_data(data: str, type_data: int) -> dict:
    dict_info = {}  # пример данных - "NAME" = "Ubuntu"
    if type_data == 0:  # /etc/release
        lines_data = data.split("\n")[:-1]
        for i in range(len(lines_data)):
            key, value = lines_data[i].replace('"', '').split("=")
            if len(dict_info) == 2:  # Если отобрали нужные значения, то выходим из цикла
                break
            elif key == "NAME":
                dict_info["os"] = value
            elif key == "VERSION":
                dict_info["version"] = value
    elif type_data == 1:  # arch
        dict_info["arch"] = data.strip()
    elif type_data == 2:  # hostnamectl
        lines_data = data.split("\n")[:-1]
        for i in range(len(lines_data)):
            key, value = lines_data[i].strip().split(": ")
            if len(dict_info) == 2:  # Если отобрали нужные значения, то выходим из цикла
                break
            if key == "Operating System":
                os_and_version = value.split(" ")
                if os_and_version[0] == "Linux":
                    # может быть такая строка Linux Mint 12.5.0 =>
                    # правильнее будет отработать os = Linux Mint и version = 12.5.0
                    dict_info["os"] = os_and_version[:1]
                    dict_info["version"] = os_and_version[2]
                else:
                    dict_info["os"] = os_and_version[0]
                    dict_info["version"] = os_and_version[1]
            elif key == "Architecture":
                dict_info["arch"] = value
    return dict_info


def write_main_os_info_to_db(list_data: list[dict], dbname: str, table_name: str, user: str, password: str, host: str,
                             port: int):
    conn = connect(dbname=dbname, user=user, password=password, host=host, port=port)
    cursor = conn.cursor()
    insert_query = sql.SQL("INSERT INTO {} ({}, {}, {}, {}) VALUES (%s, %s, %s, %s)").format(
        sql.Identifier(table_name),
        sql.Identifier("host"),
        sql.Identifier("os"),
        sql.Identifier("version"),
        sql.Identifier("arch"),
    )
    for data in list_data:
        data_to_insert = data["host"], data["os"], data["version"], data["arch"]
        print(data_to_insert)
        cursor.execute(insert_query, data_to_insert)

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Successfully inserted data into provided database {dbname} in table {table_name}")


def write_logs_to_file(logs: str) -> None:
    format_log_file = "%d-%m-%Y"  # day month year
    date_today = datetime.now().strftime(format_log_file)
    log_file = Path(f"{date_today}.log")
    mode_open_file = "w"  # By default - create a new log file
    if log_file.is_file():  # Если файл был создан ранее - продолжаем записывать в него
        mode_open_file = "a"
    with open(f"{date_today}.log", mode_open_file) as log_file:
        log_file.write(logs)


if __name__ == "__main__":
    ssh_client = SSHClient()
    try:
        machines_to_scan = get_list_machines_to_scan_from_txt("machines_to_scan.txt")
        all_machines_main_os_info = []
        for i in range(len(machines_to_scan)):
            ssh_client.set_missing_host_key_policy(AutoAddPolicy())  # Automatically add the server's host key
            ip, port, login, password = machines_to_scan[i].strip().split(" ")
            try:
                ssh_client.connect(ip, port=int(port), username=login,
                                   password=password)  # Connect to the remote server
                main_os_info = get_main_os_info(ssh_client, ip)  # Get os, version, architecture of host
                main_os_info["host"] = ip
                all_machines_main_os_info.append(main_os_info)
            except Exception as e:
                print(e)
                write_logs_to_file(f"{e}\n")

        write_main_os_info_to_db(all_machines_main_os_info, dbname=DBNAME, table_name=TABLE_NAME, host=HOST,
                                 port=PORT,
                                 user=USER, password=PASSWORD)
        # except Exception as e:
        #     pass
        # later need to add -  validate specific exceptions
    finally:
        ssh_client.close()
