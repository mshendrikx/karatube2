import requests


def whatsapp_restart_session(base_url, api_key, session):

    headers = {"x-api-key": api_key}

    url = f"{base_url}/session/restart/{session}"

    response = requests.get(url=url, headers=headers)

    if response.status_code == 200:
        return True
    else:
        return False


def whatsapp_send_message(
    base_url, api_key, session, contacts, content, content_type="string"
):

    headers = {"x-api-key": api_key}

    url = f"{base_url}/client/sendMessage/{session}"

    contatc_fail = []
    for contact in contacts:
        if content_type == "string":
            json_data = {
                "chatId": contact,
                "contentType": content_type,
                "content": content,
            }
        elif content_type == "MessageMedia":
            json_data = {
                "chatId": contact,
                "contentType": content_type,
                "content": {
                    "mimetype": "image/jpeg",
                    "data": content,
                    "filename": "image.jpg",
                },
            }
        try:
            response = requests.post(url=url, headers=headers, json=json_data)
            if response.status_code != 200:
                contatc_fail.append(contact)
        except Exception as e:
            contatc_fail.append(contact)

    return contatc_fail


def whatsapp_get_numberid(base_url, api_key, session, contact):

    headers = {"x-api-key": api_key}
    url = f"{base_url}/client/isRegisteredUser/{session}"

    phone = str(contact)
    phone = phone.replace("+", "").replace("-", "").replace(" ", "")
    json_data = {"number": phone}
    try:
        response = requests.post(url=url, headers=headers, json=json_data)
        if response.status_code != 200:
            return None
    except Exception as e:
        return None

    url = f"{base_url}/client/getNumberId/{session}"
    try:
        response = requests.post(url=url, headers=headers, json=json_data)
        if response.status_code != 200:
            return None
    except Exception as e:
        return None

    return response.json().get("result", None).get("_serialized", None)
