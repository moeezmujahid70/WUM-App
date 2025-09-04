from json import load

try:
    with open("config/config.json", encoding="utf-8") as json_file:
        data = load(json_file)
    config = data['config']
    settings = data['settings']
    limit_of_thread = config['limit_of_thread']
    login_email = config['login_email']
except Exception as e:
    print("Exeception occured at config loading : {}".format(e))

for key, item in settings.items():
    print(str(item))
    item["number_of_emails"] = 1

for key, item in settings.items():
    print(str(item))