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


def strip_group_brands(groups, brands):
    """Keep source records and expose the cleaned expression to downstream stages."""
    from cleaner import comparison_text, phrase

    result = []
    for group in groups:
        cleaned, removed = strip_brand_names(group['text'], brands)
        if not removed:
            result.append(group)
            continue
        if not cleaned or not any(char.isalnum() for char in cleaned):
            # The import still holds this source, but there is no expression to assess.
            continue
        updated = {
            **group, 'original_text': group.get('original_text', group['text']),
            'text': cleaned, 'normalized': comparison_text(cleaned),
            'removed_brands': removed,
        }
        if 'phrase_candidate' in updated:
            updated['phrase_candidate'] = phrase(cleaned)
        result.append(updated)
    return result
