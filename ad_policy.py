"""Apply only explicitly confirmed brand exclusions; retain original records."""
import re


def matched_brand(text,brands):
    for brand in brands or []:
        letters=[re.escape(c) for c in str(brand) if c.isalnum()]
        if letters and re.search(r'(?<!\w)'+r'[\W_]*'.join(letters)+r'(?!\w)',str(text),re.I):return brand
    return None


def strip_brand_names(text,brands):
    """Remove named brand tokens only; product suitability must be assessed later."""
    cleaned=str(text);removed=[]
    for brand in brands or []:
        letters=[re.escape(c) for c in str(brand) if c.isalnum()]
        if not letters:continue
        pattern=r'(?<!\w)'+r'[\W_]*'.join(letters)+r'(?!\w)'
        cleaned,count=re.subn(pattern,' ',cleaned,flags=re.I)
        if count:removed.append(str(brand))
    return re.sub(r'\s+',' ',cleaned).strip(),removed


def apply_brand_exclusions(groups,decisions,product):
    results={i:dict(r) for i,r in decisions.items()}
    for g in groups:
        brand=matched_brand(g['text'],product.get('excluded_brands',[]))
        if brand:
            results[g['group_id']]={**results.get(g['group_id'],{}),'ad_status':'exclude','copy_status':'exclude',
                'ad_reason':'用户确认排除他牌：'+brand,'copy_reason':'本品文案不使用他牌名'}
    return results
