def limit(value, min, max):
    if value > max:
        return max
    elif value < min:
        return min
    else:
        return value


def dictget(dic, key, default=None):
    """
    Recursive get from dictionary.

    :param dic: source dictionary
    :param key: key or keylist
    :return: value
    """
    v = None
    try:
        if not isinstance(key, (tuple, list)):  # normal get from dictionary
            v = dic[key]
        else:
            v = dic
            for k in key:  # loop over keys
                v = v[k]
    except (KeyError, IndexError, TypeError):
        v = None

    if default is not None and v is None:
        return default
    else:
        return v

