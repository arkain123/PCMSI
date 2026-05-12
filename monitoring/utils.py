import hmac
import hashlib


def verify_signature(agent, body, timestamp, received_signature):
    message = body + timestamp.encode()

    expected_signature = hmac.new(
        agent.secret_key.encode(),
        message,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, received_signature)


def deep_merge(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override

    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result