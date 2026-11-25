#!/usr/bin/env python3
"""
Unit and Integration Tests for Cephalo Multilingual Classifier & Quarantine Architecture.
"""

import pytest
from cephalo.learning.multilingual_classifier import MultilingualClassifier
from cephalo.learning.specialties_manager import SpecialtiesManager


@pytest.fixture
def classifier():
    return MultilingualClassifier()


def test_multilingual_hungarian_preference_and_critique(classifier):
    # Hungarian critique + preference + hardware
    text = "A tévém egy Sample 4K TV, és a szaturált, élénk 4K-t preferálom, utálom a lassú szürke filmeket."
    res = classifier.classify(text)
    assert res.is_durable is True
    assert res.is_quarantined is False
    assert res.detected_language == "hu"
    assert "critique_negative_filter" in res.detected_categories or "hardware_spec" in res.detected_categories


def test_multilingual_hungarian_communication_rule(classifier):
    text = "Mostantól mindig magyarul és angolul válaszolj, sallangmentes stílusban."
    res = classifier.classify(text)
    assert res.is_durable is True
    assert res.detected_language == "hu"
    assert "communication_style" in res.detected_categories
    assert "workflow_rule" in res.detected_categories


def test_multilingual_hungarian_automotive_design(classifier):
    text = "Az autó livery dizájnhoz használjunk JGTC stílust a Subaru GF8-on."
    res = classifier.classify(text)
    assert res.is_durable is True
    assert res.category == "automotive_design"


def test_multilingual_german_preference(classifier):
    text = "Ich bevorzuge für meinen Arbeitsplatz ein dunkles Theme und sauberen Code."
    res = classifier.classify(text)
    assert res.is_durable is True
    assert res.detected_language == "de"


def test_quarantine_single_turn_commands(classifier):
    # Quick commands must be quarantined
    assert classifier.classify("Run pytest on tests/test_storage.py and see if it passes.").is_quarantined is True
    assert classifier.classify("Nézd meg a commitot, és javítsd ki a hibát.").is_quarantined is True
    assert classifier.classify("try again").is_quarantined is True
    assert classifier.classify("Is it in this commit? feat(search): implement BM25F ranking").is_quarantined is True


def test_quarantine_large_task_payloads(classifier):
    # Multi-thousand character audit pastes must be quarantined to prevent vector dilution
    audit_text = "I created an audit with Claude. Look at it: " + ("Cephalo code review issue details. " * 50)
    res = classifier.classify(audit_text)
    assert res.is_quarantined is True
    assert res.is_durable is False
    assert "Large task payload" in res.rationale


def test_specialties_manager_rejects_conversational_text():
    sm = SpecialtiesManager()
    
    # 1. Full sentence prompt
    res = sm.auto_create_specialty("the-sign-in-and-get-started-for-free-buttons-are-still-shown-and-i-cant-log-out")
    assert res["created"] is False
    assert "Rejected conversational text" in res["error"]
    
    # 2. Hungarian sentence prompt
    res_hu = sm.auto_create_specialty("nem működik a bejelentkezés gomb és a navigáció")
    assert res_hu["created"] is False
    assert "Rejected conversational text" in res_hu["error"]
    
    # 3. auto_discover_and_create on conversational text returns empty
    discover_res = sm.auto_discover_and_create("Research and investigate the reddit post and the article!")
    assert len(discover_res) == 0
