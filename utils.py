import re
import var
import random
import json
import spintax
from pyautogui import alert, password, confirm

def prepare_html(body):
    # print(body)
    mails = re.findall('[\w\.-]+@[\w\.-]+\.\w+', body)
    urls = re.findall('https?://[^\s<>"]+|www\.[^\s<>"]+', body)
    for item in urls:
        try:
            a_tag = '<a href="{}">{}</a>'.format(item, item)
            if '<{}>'.format(item) in body:
                body = body.replace('<{}>'.format(item), a_tag)
            else:
                body = body.replace(' {}'.format(item), ' ' + a_tag)
                body = body.replace('\n{}'.format(item), '\n' + a_tag)
        except:
            pass
    for item in mails:
        try:
            a_tag = ' <a href="mailto:{}">{}</a>'.format(item, item)
            body = body.replace(' {}'.format(item), a_tag)
        except:
            pass
    body = body.replace("\n", '<br>')
    # print(body)
    html = """<!doctype html>

            <html lang="en">
            <head>
            <meta charset="utf-8">

            <title>The HTML5 Herald</title>
            <meta name="description" content="The HTML5 Herald">
            <meta name="author" content="SitePoint">


            </head>

            <body>
            <p>{}</p>
            
            </body>
            </html>""".format(body)

    return html

def update_config_json():
    try:
        data = {'config': {'limit_of_thread': var.limit_of_thread, 'login_email': var.login_email, 'subject': var.compose_email_subject, 'body': var.compose_email_body}, 'settings': var.settings}
        with open(var.config_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)
        print('config updated')
    except Exception as e:
        print('Exception occurred at update_config_json : {}'.format(e))
        alert(text='Exception occurred at update_config_json : {}'.format(e), title='Alert', button='OK')

def format_email(text, FIRSTFROMNAME, LASTFROMNAME, TONAME):
    text = text.replace('[FIRSTFROMNAME]', str(FIRSTFROMNAME))
    text = text.replace('[LASTFROMNAME]', str(LASTFROMNAME))
    text = text.replace('[TONAME]', str(TONAME))
    spintax_bracket = re.compile('(?<!\\\\)((?:\\\\{2})*)\\{([^{}]+)(?<!\\\\)((?:\\\\{2})*)\\}')
    used_sentences = set()

    def _replace_spintax(match):
        prefix, options, suffix = match.groups()
        options_list = options.split('|')
        available_options = [option for option in options_list if option not in used_sentences]
        if available_options:
            chosen_option = random.choice(available_options)
            used_sentences.add(chosen_option)
            return prefix + chosen_option + suffix
        return prefix + random.choice(options_list) + suffix
    while True:
        new_text = re.sub(spintax_bracket, _replace_spintax, text)
        if new_text == text:
            break
        text = new_text
    text = re.sub('\\\\([{}|])', '\\1', text)
    text = re.sub('\\\\{2}', '\\\\', text)
    return text
if __name__ == '__main__':
    print(__name__)