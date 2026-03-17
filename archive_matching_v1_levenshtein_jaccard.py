"""
ARCHIVED: Original Market Matching Attempt (Levenshtein + Jaccard)
Date: March 17, 2026
Status: Superseded by semantic embedding methods

This module contains the original string-similarity based matching approach.
It used:
- Levenshtein distance (sequence similarity)
- Jaccard similarity (keyword overlap)
- Combined scoring with 60/40 weights

Results: 18 total matches (11 mineral_rights, 7 zelensky_suit)
- Many false positives due to lack of semantic understanding
- Missed paraphrased matches
- Issues: "Trump ends war" vs. "Ukraine ceasefire" marked as different events

Replaced by: Semantic embeddings approach in data_source_explore.ipynb
"""

import pandas as pd
import re
from difflib import SequenceMatcher
from nltk.corpus import stopwords

STOPWORDS = set(stopwords.words('english'))


def normalize_market_text(text, remove_boilerplate=True, aggressive=False):
    """
    Normalize market text for comparison.
    
    aggressive=False (default): preserves punctuation/hyphens for better context
    aggressive=True: removes all special chars (old behavior)
    """
    if pd.isna(text) or not text:
        return ""
    
    text = str(text).strip().lower()
    
    if remove_boilerplate:
        # Light boilerplate removal - only obvious fillers
        boilerplate = [
            r'^\s*will\s+', r'\bwill the\b', r'\bis it true that\b',
        ]
        for pattern in boilerplate:
            text = re.sub(pattern, ' ', text, flags=re.I)
    
    if aggressive:
        # Remove ALL special chars (old behavior)
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
    else:
        # Preserve hyphens, commas, quotes - they convey structure
        text = re.sub(r'[^\w\s\-\',;().]', ' ', text, flags=re.UNICODE)
    
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_key_nouns(text, min_length=3):
    """Extract key nouns/content words that identify the event."""
    normalized = normalize_market_text(text, remove_boilerplate=True, aggressive=False)
    words = re.findall(r'\b\w+\b', normalized)
    key_words = [w for w in words if len(w) >= min_length and w not in STOPWORDS]
    return set(key_words)


def semantic_similarity_score(text1, text2, method='levenshtein'):
    """Compute similarity: 'levenshtein' (sequence) or 'keyword_overlap' (Jaccard)."""
    norm1 = normalize_market_text(text1)
    norm2 = normalize_market_text(text2)
    
    if method == 'levenshtein':
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    elif method == 'keyword_overlap':
        keys1 = extract_key_nouns(text1)
        keys2 = extract_key_nouns(text2)
        if not keys1 or not keys2:
            return 0.0
        intersection = len(keys1 & keys2)
        union = len(keys1 | keys2)
        return intersection / union if union > 0 else 0.0
    
    return 0.0


def match_markets_for_event(pm_df, k_df, slug, threshold_lev=0.70, threshold_jaccard=0.30):
    """
    Match PM and Kalshi markets, preserving original titles for verification.
    
    DEPRECATED: Use semantic embedding methods for better accuracy.
    
    Returns:
        DataFrame with original market titles + similarity scores
    """
    
    if pm_df is None or k_df is None or len(pm_df) == 0 or len(k_df) == 0:
        return pd.DataFrame()
    
    matches = []
    
    for _, pm_row in pm_df.iterrows():
        pm_id = pm_row.get('id', pm_row.get('market_id', 'N/A'))
        pm_question_original = pm_row.get('question', '')
        
        best_match = None
        best_lev_score = 0
        best_jaccard_score = 0
        best_k_row = None
        
        for _, k_row in k_df.iterrows():
            k_ticker = k_row.get('ticker', 'N/A')
            k_title_original = k_row.get('title', '')
            k_yes = k_row.get('yes_sub_title', '')
            k_no = k_row.get('no_sub_title', '')
            k_text_combined = f"{k_title_original} {k_yes} {k_no}"
            
            # Compute similarity scores using LESS aggressive normalization
            lev_score = semantic_similarity_score(pm_question_original, k_text_combined, method='levenshtein')
            jaccard_score = semantic_similarity_score(pm_question_original, k_text_combined, method='keyword_overlap')
            
            # Track best match
            combined_score = 0.6 * lev_score + 0.4 * jaccard_score
            if combined_score > best_match[2] if best_match else combined_score > 0:
                best_match = (k_ticker, combined_score, lev_score, jaccard_score)
                best_k_row = k_row
                best_lev_score = lev_score
                best_jaccard_score = jaccard_score
        
        # Record match if meets thresholds
        if best_match and (best_lev_score >= threshold_lev or best_jaccard_score >= threshold_jaccard):
            k_ticker, combined, lev_score, jaccard_score = best_match
            
            # Classify match type
            if lev_score >= 0.85:
                match_type = "HIGH_CONFIDENCE"
            elif lev_score >= threshold_lev or jaccard_score >= 0.5:
                match_type = "MEDIUM_CONFIDENCE"
            else:
                match_type = "LOW_CONFIDENCE"
            
            matches.append({
                'pm_id': pm_id,
                'pm_question': pm_question_original,
                'k_ticker': k_ticker,
                'k_title': best_k_row.get('title', ''),
                'k_yes_subtitle': best_k_row.get('yes_sub_title', ''),
                'k_no_subtitle': best_k_row.get('no_sub_title', ''),
                'levenshtein_score': round(lev_score, 3),
                'jaccard_score': round(jaccard_score, 3),
                'combined_score': round(combined, 3),
                'match_type': match_type,
                'slug': slug
            })
    
    return pd.DataFrame(matches) if matches else pd.DataFrame()


if __name__ == "__main__":
    """
    Example usage (deprecated):
    
    pm_df = pd.read_csv('exports/mineral_rights_pm_topics.csv')
    k_df = pd.read_csv('exports/mineral_rights_k_topics.csv')
    
    matches = match_markets_for_event(pm_df, k_df, 'mineral_rights')
    print(f"Found {len(matches)} matches")
    matches.to_csv('old_matches.csv', index=False)
    """
    pass
