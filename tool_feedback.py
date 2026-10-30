"""Handwritten feedback-shaping example, not an AT-AT reproduction."""
import json

def usage_status(used, limit):
    if used < 0 or limit < 0:
        raise ValueError('usage and limit must be nonnegative')
    return {'used': used, 'limit': limit, 'remaining': max(limit-used,0), 'over_limit': used>limit}

if __name__=='__main__':
    assert usage_status(12,10)=={'used':12,'limit':10,'remaining':0,'over_limit':True}
    assert usage_status(10,10)['over_limit'] is False
    assert usage_status(3,10)['remaining']==7
    print(json.dumps({'scope':'Handwritten tool feedback example, not the AT-AT optimizer','before':{'used':12,'limit':10},'after':usage_status(12,10),'checks':'3 passed'},indent=2))
