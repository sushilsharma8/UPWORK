#!/usr/bin/env python3
"""
Enhanced Resume Parser
A comprehensive resume parsing solution with improved accuracy and API capabilities.
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import uuid
from datetime import datetime, timedelta

import spacy
import pdfplumber
import docx
from collections import defaultdict
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# NLTK data is downloaded during Docker build
# No need to download at runtime in Lambda

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.error("SpaCy model 'en_core_web_sm' not found. Please run: python -m spacy download en_core_web_sm")
    exit(1)

# Enhanced regex patterns
PHONE_REGEX = re.compile(
    r'(?:\+?1[-.\s]?)?(?:\(?([0-9]{3})\)?[-.\s]?)?([0-9]{3})[-.\s]?([0-9]{4})'
    r'|(?:\+?[1-9]\d{0,3}[-.\s]?)?(?:\(?([0-9]{2,4})\)?[-.\s]?)?([0-9]{2,4})[-.\s]?([0-9]{2,4})[-.\s]?([0-9]{2,4})'
    r'|(?:\+?[1-9]\d{0,3}[-.\s]?)?([0-9]{7,15})'
)

EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# LinkedIn profile URLs (with or without protocol/www)
LINKEDIN_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?linkedin\.com/[^\s,;]+',
    re.IGNORECASE
)

# Enhanced date patterns
DATE_PATTERNS = [
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
    r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
    r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',
    r'\d{4}',
    r'(?:present|current|now)'
]

DATE_RANGE_REGEX = re.compile(
    r'(?i)(?:' + '|'.join(DATE_PATTERNS) + r')\s*(?:-|\u2013|\u2014|\s*to\s*|\s*until\s*)\s*(?:' + '|'.join(DATE_PATTERNS) + r'|present|current|now)',
    re.IGNORECASE
)

# Enhanced section keywords
SECTION_KEYWORDS = {
    "contact": [
        "contact", "contact information", "personal information", "personal details"
    ],
    "professional_summary": [
        "professional summary", "summary", "profile", "career summary", 
        "professional profile", "executive summary", "objective", "career objective"
    ],
    "experience": [
        "experience", "professional experience", "work experience",
        "employment history", "career history", "work history", "employment",
        "professional background", "work background"
    ],
    "education": [
        "education", "academic background", "academic qualifications",
        "academic achievements", "educational background", "academic credentials",
        "degrees", "qualifications"
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "competencies",
        "expertise", "technologies", "tools", "programming languages"
    ],
    "certifications": [
        "certifications", "certification", "licenses", "license",
        "credentials", "professional certifications"
    ],
    "projects": [
        "projects", "key projects", "notable projects", "project experience"
    ],
    "awards": [
        "awards", "honors", "achievements", "recognition", "accomplishments"
    ]
}

# Common job titles and skills
JOB_TITLE_KEYWORDS = [
    "engineer", "developer", "manager", "consultant", "analyst", "specialist",
    "architect", "lead", "officer", "director", "scientist", "designer",
    "administrator", "associate", "intern", "principal", "senior", "junior",
    "staff", "product", "program", "coordinator", "supervisor", "executive",
    "vice president", "ceo", "cto", "cfo", "founder", "co-founder"
]

# Comprehensive skills database
TECH_SKILLS = [
    # Programming Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "php", "ruby", "go", "rust", "swift", "kotlin", "scala", "r", "matlab", "perl", "bash", "powershell",
    
    # Web Technologies
    "react", "angular", "vue", "node.js", "express", "django", "flask", "spring", "laravel", "symfony", "asp.net", "jquery", "bootstrap", "sass", "less", "webpack", "babel",
    
    # Cloud & DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "terraform", "ansible", "chef", "puppet", "git", "github", "gitlab", "bitbucket", "ci/cd", "devops", "microservices",
    
    # Databases
    "sql", "mysql", "postgresql", "mongodb", "redis", "cassandra", "elasticsearch", "oracle", "sqlite", "mariadb", "dynamodb", "neo4j", "influxdb",
    
    # Testing & QA
    "selenium", "cypress", "jest", "mocha", "junit", "testng", "pytest", "postman", "jmeter", "loadrunner", "katalon", "appium", "testing", "qa", "automation", "tosca",
    
    # Salesforce & CRM
    "salesforce", "apex", "visualforce", "lightning", "salesforce admin", "salesforce developer", "salesforce architect", "crm", "marketo", "hubspot",
    
    # Mobile Development
    "android", "ios", "react native", "flutter", "xamarin", "ionic", "cordova", "phonegap",
    
    # Data Science & Analytics
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "spark", "hadoop", "hive", "pig", "kafka", "airflow", "jupyter", "tableau", "power bi", "excel",
    
    # Operating Systems
    "linux", "windows", "macos", "unix", "ubuntu", "centos", "redhat", "debian", "fedora",
    
    # Methodologies & Frameworks
    "agile", "scrum", "kanban", "waterfall", "lean", "six sigma", "itil", "pmp", "prince2",
    
    # Other Technologies
    "api", "rest", "soap", "graphql", "json", "xml", "yaml", "html", "css", "xml", "yaml", "nginx", "apache", "tomcat", "iis"
]

@dataclass
class ContactInfo:
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None

@dataclass
class JobExperience:
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    responsibilities: List[str] = None
    achievements: List[str] = None

    def __post_init__(self):
        if self.responsibilities is None:
            self.responsibilities = []
        if self.achievements is None:
            self.achievements = []

@dataclass
class Education:
    degree: Optional[str] = None
    field: Optional[str] = None
    institution: Optional[str] = None
    location: Optional[str] = None
    graduation_date: Optional[str] = None
    gpa: Optional[str] = None

@dataclass
class ParsedResume:
    file_path: str
    contact: ContactInfo
    professional_summary: Optional[str] = None
    experience: List[JobExperience] = None
    education: List[Education] = None
    skills: List[str] = None
    certifications: List[str] = None
    projects: List[str] = None
    awards: List[str] = None
    raw_text: Optional[str] = None
    confidence_score: float = 0.0

    def __post_init__(self):
        if self.experience is None:
            self.experience = []
        if self.education is None:
            self.education = []
        if self.skills is None:
            self.skills = []
        if self.certifications is None:
            self.certifications = []
        if self.projects is None:
            self.projects = []
        if self.awards is None:
            self.awards = []

class ResumeParser:
    """Enhanced resume parser with improved accuracy and modularity."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.nlp = nlp  # Store spaCy model for use in class methods
        try:
            self.stop_words = set(stopwords.words('english'))
        except LookupError:
            # Fallback to basic English stopwords if NLTK data is not available
            logger.warning("NLTK stopwords not found, using fallback stopwords")
            self.stop_words = {
                'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
                'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
                'to', 'was', 'will', 'with', 'i', 'you', 'we', 'they', 'this',
                'these', 'those', 'or', 'but', 'if', 'when', 'where', 'why',
                'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
                'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
                'same', 'so', 'than', 'too', 'very', 'can', 'could', 'should',
                'would', 'may', 'might', 'must', 'shall', 'do', 'does', 'did',
                'have', 'had', 'having', 'been', 'being', 'am', 'are', 'is',
                'was', 'were', 'be', 'being', 'been', 'have', 'has', 'had',
                'having', 'do', 'does', 'did', 'will', 'would', 'could',
                'should', 'may', 'might', 'must', 'shall'
            }
        
    def extract_text_from_pdf(self, path: str) -> str:
        """Extract text from PDF with improved error handling."""
        try:
            text = ""
            with pdfplumber.open(path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_num + 1}: {e}")
                        continue
            return text.strip()
        except Exception as e:
            logger.error(f"Error reading PDF {path}: {e}")
            return ""

    def extract_text_from_docx(self, path: str) -> str:
        """Extract text from DOCX with improved error handling.

        Note: Many modern resume templates put the candidate's name, email, and
        phone number in the document header. By default, `python-docx` exposes
        body paragraphs via `doc.paragraphs` but header/footer text must be
        read explicitly from `section.header` / `section.footer`.
        """
        try:
            doc = docx.Document(path)
            parts: List[str] = []

            # 1) Collect header text (where contact info often lives)
            # We collect from all sections, de-duplicating later.
            try:
                for section in doc.sections:
                    header = section.header
                    if not header:
                        continue
                    for para in header.paragraphs:
                        text = para.text.strip()
                        if text:
                            parts.append(text)
            except Exception as e:
                # Header parsing issues shouldn't break entire extraction
                logger.warning(f"Error reading DOCX headers for {path}: {e}")

            # 2) Collect main body paragraphs
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    parts.append(text)

            # 3) Optionally collect footer text (rarely contains contact info,
            # but cheap to include and may add missing details)
            try:
                for section in doc.sections:
                    footer = section.footer
                    if not footer:
                        continue
                    for para in footer.paragraphs:
                        text = para.text.strip()
                        if text:
                            parts.append(text)
            except Exception as e:
                logger.warning(f"Error reading DOCX footers for {path}: {e}")

            # De-duplicate while preserving order to avoid repeated header text
            seen = set()
            unique_parts: List[str] = []
            for t in parts:
                if t not in seen:
                    seen.add(t)
                    unique_parts.append(t)

            return "\n".join(unique_parts).strip()
        except Exception as e:
            logger.error(f"Error reading DOCX {path}: {e}")
            return ""

    def extract_name(self, text: str) -> str | None:
        """Extract name from resume text with improved accuracy using pattern-based validation."""
        
        def is_valid_name(candidate: str) -> bool:
            """Validate if a candidate string is likely a real name using pattern-based checks."""
            if not candidate:
                return False
            
            candidate = candidate.strip()
            words = candidate.split()
            
            # Structural validation: name length (2-4 words typical for names)
            if not (2 <= len(words) <= 4):
                return False
            
            # Pattern validation: names should be primarily alphabetic (allow hyphens and apostrophes)
            cleaned = re.sub(r"['-]", "", candidate)
            if not cleaned.replace(" ", "").isalpha():
                return False
            
            # Pattern validation: proper noun format - each word should start with capital
            original_words = candidate.split()
            for word in original_words:
                if not word[0].isupper():
                    return False
                # Names don't have mixed case within words (e.g., "JavaScript" is not a name)
                if len(word) > 1 and re.search(r'[a-z][A-Z]', word):
                    return False
            
            # Pattern validation: reject if it contains technical patterns
            # Check for common technical suffixes/patterns
            candidate_lower = candidate.lower()

            # Reject obvious job-title phrases like "Front End UI Developer", "Software Engineer", etc.
            # We keep this pattern small and focused so it stays maintainable.
            if re.search(r"\b(developer|engineer|manager|consultant|analyst|tester|architect|lead|designer|specialist|intern)\b", candidate_lower):
                return False
            
            # Reject words ending in "ing" (gerunds/verbs like "Testing", "Loading", "Processing")
            # These are almost never names
            for word in words:
                word_lower = word.lower()
                if word_lower.endswith('ing') and len(word_lower) >= 5:
                    return False
            
            # Reject if it contains other technical word patterns
            # Technical terms often have specific patterns (e.g., "Framework", "API")
            # Check for words ending in common technical suffixes
            technical_suffixes = ['tion', 'ment', 'ness', 'ity', 'ism']
            for word in words:
                word_lower = word.lower()
                # Very long words (>12 chars) with technical suffixes are suspicious
                if len(word_lower) > 12:
                    for suffix in technical_suffixes:
                        if word_lower.endswith(suffix) and len(word_lower) > len(suffix) + 5:
                            return False
            
            # Pattern validation: reject concatenated words (no spaces in long strings)
            # Names should have proper spacing between words
            for word in words:
                # Very long words (>15 chars) are suspicious for names
                if len(word) > 15:
                    return False
                # Check for mixed case patterns that suggest concatenation
                if re.search(r'[A-Z][a-z]{5,}[A-Z]', word):
                    return False
            
            # Pattern validation: reject if it looks like a section header
            # Section headers often have all caps or specific patterns, but many resumes
            # use ALL CAPS for the candidate name on the first line (e.g., "BALRAJ REDDY").
            if candidate.isupper():
                # Allow short 2–3 word ALL CAPS strings that look like real names
                header_like_keywords = {
                    "professional", "summary", "experience", "education",
                    "skills", "projects", "certifications", "objective",
                    "profile", "resume", "curriculum", "vitae"
                }
                word_set = {w for w in words}
                # If it obviously contains header keywords, reject
                if word_set & {w.upper() for w in header_like_keywords}:
                    return False
                # Otherwise, only reject long ALL CAPS phrases; keep short ones as valid
                if len(words) > 3 or len(candidate) > 40:
                    return False
            
            # Pattern validation: reject if it contains numbers or special chars (except hyphens/apostrophes)
            if re.search(r'[0-9]', candidate):
                return False
            
            # Pattern validation: reject if words are too short (single letter words are rare in names)
            for word in words:
                if len(word) == 1 and word.lower() not in ['i', 'o']:  # Allow 'I' and 'O' as initials
                    return False
            
            return True
        
        # Only scan top section (first 8 lines)
        header = "\n".join(text.split("\n")[:8]).strip()
        lines = [line.strip() for line in header.split("\n") if line.strip()]
        
        # Priority 1: First non-empty line (most resumes have name here)
        if lines:
            first_line = lines[0].strip()
            # Special, slightly looser rule for the very first line: many names include
            # a lowercase middle name or mixed casing (e.g., "Calvin raj Namburi"),
            # and some resumes only have a single given name on the first line (e.g., "Mukesh").
            # Accept if:
            #   - 1–4 alphabetic words
            #   - does NOT contain obvious job-title or section-header keywords
            #   - does not contain digits/symbols
            first_words = first_line.split()
            header_like_keywords = {
                "professional", "summary", "experience", "education",
                "skills", "projects", "certifications", "objective",
                "profile", "resume", "curriculum", "vitae"
            }
            if 2 <= len(first_words) <= 4:
                if all(re.sub(r"['-]", "", w).isalpha() for w in first_words):
                    lower_first = first_line.lower()
                    if not any(kw in lower_first for kw in JOB_TITLE_KEYWORDS) and not any(
                        kw in lower_first for kw in header_like_keywords
                    ):
                        # Looks like a reasonable multi-word name header; accept directly
                        return first_line
            elif len(first_words) == 1:
                single = first_words[0]
                cleaned_single = re.sub(r"['-]", "", single)
                lower_single = cleaned_single.lower()
                # Single-word name heuristic: capitalized, alphabetic, reasonable length, and
                # not an obvious section/header keyword.
                if (
                    cleaned_single.isalpha()
                    and single[0].isupper()
                    and 3 <= len(cleaned_single) <= 20
                    and lower_single not in header_like_keywords
                    and lower_single not in JOB_TITLE_KEYWORDS
                ):
                    return first_line
            # Otherwise fall back to the stricter validator
            if is_valid_name(first_line):
                return first_line
        
        # Run spaCy NER only on the header
        doc = self.nlp(header)
        
        # Priority 2: spaCy PERSON entities with validation (still constrained to header)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                candidate = ent.text.strip()
                if is_valid_name(candidate):
                    return candidate
        
        # Priority 3: Check remaining lines (2nd–5th) as a fallback
        for line in lines[1:5]:
            if line and is_valid_name(line):
                return line
        
        return None

    def verify_name_with_email(self, name: str, email: str) -> bool:
        """Verify if extracted name matches patterns in email address."""
        if not name or not email or '@' not in email:
            return False
        
        # Get local part of email (before @)
        local_part = email.split('@')[0].lower()
        
        # Normalize name: convert to lowercase and extract name parts
        name_lower = name.lower().strip()
        name_words = [word.lower() for word in name.split() if word.isalpha()]
        
        if len(name_words) < 2:
            return False
        
        # Pattern 1: Check if name words appear in email (with separators)
        # Common separators in emails: ., _, -, (none)
        separators = ['.', '_', '-', '']
        
        for sep in separators:
            if sep:
                # Check if email contains name parts separated by delimiter
                # e.g., "john.doe" matches "John Doe"
                email_parts = local_part.split(sep)
                if len(email_parts) >= 2:
                    # Check if at least 2 name words appear in email parts
                    matches = 0
                    for name_word in name_words:
                        for email_part in email_parts:
                            # Exact match or email part starts with name word (e.g., "john" matches "johnsmith")
                            if name_word == email_part or email_part.startswith(name_word):
                                matches += 1
                                break
                    if matches >= 2:
                        return True
        
        # Pattern 2: Check if name words appear consecutively in email (no separator)
        # e.g., "johndoe" matches "John Doe"
        name_concat = ''.join(name_words)
        if name_concat in local_part:
            return True
        
        # Pattern 3: Check if first letters of name words match email pattern
        # e.g., "jd" or "jdoe" matches "John Doe"
        first_letters = ''.join([word[0] for word in name_words])
        if first_letters in local_part and len(first_letters) >= 2:
            return True
        
        # Pattern 4: Check if first name + last name initial or vice versa
        # e.g., "johnd" or "jdoe" matches "John Doe"
        if len(name_words) >= 2:
            first_name = name_words[0]
            last_name = name_words[-1]
            # Pattern: firstname + lastname initial
            if first_name + last_name[0] in local_part:
                return True
            # Pattern: firstname initial + lastname
            if first_name[0] + last_name in local_part:
                return True
        
        # Pattern 5: Check if individual name words appear in email
        # At least 2 name words should appear in email
        matches = 0
        for name_word in name_words:
            if len(name_word) >= 3:  # Only check words with 3+ chars
                if name_word in local_part:
                    matches += 1
        if matches >= 2:
            return True
        
        return False

    def extract_name_from_email(self, email: str) -> str | None:
        """Extract name from email address using pattern-based validation."""
        if not email or '@' not in email:
            return None
        
        local_part = email.split('@')[0].lower()
        
        # Pattern 1: Separated by common delimiters (e.g., "john.doe", "john_doe", "john-doe")
        separators = ['.', '_', '-']
        for sep in separators:
            if sep in local_part:
                parts = local_part.split(sep)
                # Filter out non-name parts
                filtered_parts = []
                for part in parts:
                    # Skip pure numbers, very short parts, or parts with numbers
                    if part.isdigit() or len(part) < 2 or re.search(r'\d', part):
                        continue
                    # Only keep alphabetic parts
                    if part.isalpha():
                        filtered_parts.append(part)
                
                # Need at least 2 parts to form a name
                if len(filtered_parts) >= 2:
                    name_candidate = ' '.join(filtered_parts).title()
                    # Use the same validation as extract_name
                    if self._is_valid_name_format(name_candidate):
                        return name_candidate
        
        # Pattern 2: camelCase (e.g., "JohnDoe" -> "John Doe")
        if re.search(r'[a-z][A-Z]', local_part):
            parts = re.split(r'([A-Z][a-z]+)', local_part)
            filtered_parts = [p for p in parts if p and len(p) >= 2 and p.isalpha()]
            if len(filtered_parts) >= 2:
                name_candidate = ' '.join(filtered_parts).title()
                if self._is_valid_name_format(name_candidate):
                    return name_candidate
        
        # Pattern 3: All lowercase concatenated (e.g., "bhavaniakuthota" -> "Bhavani Akuthota")
        # Try intelligent splitting for common name patterns
        if local_part.isalpha() and local_part.islower():
            length = len(local_part)
            # Typical names: 8-20 characters when concatenated
            if 8 <= length <= 20:
                # Try splitting at various points
                # Common patterns: first name (4-8 chars) + last name (4-10 chars)
                for split_point in range(4, min(10, length - 3)):
                    first_part = local_part[:split_point]
                    second_part = local_part[split_point:]
                    
                    # Both parts should be reasonable length (3+ chars each)
                    if len(first_part) >= 3 and len(second_part) >= 3:
                        name_candidate = f"{first_part.title()} {second_part.title()}"
                        if self._is_valid_name_format(name_candidate):
                            return name_candidate
        
        return None

    def _is_valid_name_format(self, candidate: str) -> bool:
        """Helper function to validate name format (reused from extract_name logic)."""
        if not candidate:
            return False
        
        candidate = candidate.strip()
        words = candidate.split()
        
        # Structural validation: name length (2-4 words typical for names)
        if not (2 <= len(words) <= 4):
            return False
        
        # Pattern validation: names should be primarily alphabetic
        cleaned = re.sub(r"['-]", "", candidate)
        if not cleaned.replace(" ", "").isalpha():
            return False
        
        # Pattern validation: proper noun format - each word should start with capital
        for word in words:
            if not word[0].isupper():
                return False
            # Names don't have mixed case within words
            if len(word) > 1 and re.search(r'[a-z][A-Z]', word):
                return False
        
        # Pattern validation: reject words ending in "ing" (gerunds/verbs)
        for word in words:
            word_lower = word.lower()
            if word_lower.endswith('ing') and len(word_lower) >= 5:
                return False
        
        # Pattern validation: reject very long words
        for word in words:
            if len(word) > 15:
                return False
            if re.search(r'[A-Z][a-z]{5,}[A-Z]', word):
                return False
        
        # Reject obvious job-title phrases (e.g., "... Developer", "... Engineer") to
        # avoid treating email-based constructs like "Beer Amuideveloper" as names.
        candidate_lower = candidate.lower()
        for kw in JOB_TITLE_KEYWORDS:
            if kw in candidate_lower:
                return False
        
        # Pattern validation: reject if it contains numbers
        if re.search(r'[0-9]', candidate):
            return False
        
        return True

    def extract_contact_info(self, text: str) -> ContactInfo:
        """Extract contact information with improved accuracy."""
        contact = ContactInfo()
        
        # Extract email
        email_match = EMAIL_REGEX.search(text)
        if email_match:
            contact.email = email_match.group(0).lower()
        
        # Extract phone
        phone_matches = PHONE_REGEX.findall(text)
        if phone_matches:
            # Clean and validate phone numbers
            for match in phone_matches:
                phone = ''.join(filter(str.isdigit, ''.join(match)))
                if 7 <= len(phone) <= 15:
                    contact.phone = phone
                    break
        
        # Extract LinkedIn profile (if present anywhere in text)
        linkedin_match = LINKEDIN_REGEX.search(text)
        if linkedin_match:
            linkedin_url = linkedin_match.group(0).strip().rstrip('.,);]')
            # Normalise to include protocol
            if not linkedin_url.lower().startswith(("http://", "https://")):
                linkedin_url = "https://" + linkedin_url
            contact.linkedin = linkedin_url
        
        # Extract name using improved method (header-based)
        contact.name = self.extract_name(text)
        
        # # Verify extracted name with email (if both exist)
        # if contact.name and contact.email:
        #     if not self.verify_name_with_email(contact.name, contact.email):
        #         # Name doesn't match email pattern - might be incorrect, try extracting from email
        #         email_name = self.extract_name_from_email(contact.email)
        #         if email_name:
        #             # If email-based name is found and it's different, prefer email-based one
        #             # (email is more reliable for name extraction)
        #             contact.name = email_name
        # elif not contact.name and contact.email:
        # No name found in text, try extracting from email
        if not contact.name and contact.email:
            contact.name = self.extract_name_from_email(contact.email)
        
        # Extract location (only from header, be conservative - return None if not confident)
        extracted_name = contact.name
        
        # Common US state abbreviations
        us_states = {
            'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga', 'hi', 'id', 'il', 'in',
            'ia', 'ks', 'ky', 'la', 'me', 'md', 'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv',
            'nh', 'nj', 'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc', 'sd', 'tn',
            'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy', 'dc'
        }
        
        # Common country names and abbreviations
        countries = {
            'usa', 'us', 'united states', 'uk', 'united kingdom', 'canada', 'india', 'australia',
            'germany', 'france', 'spain', 'italy', 'china', 'japan', 'brazil', 'mexico',
            'singapore', 'uae', 'south africa', 'netherlands', 'sweden', 'norway', 'denmark'
        }
        
        def is_valid_location(candidate: str) -> bool:
            """Validate if a candidate string is likely a real location using pattern-based validation."""
            if not candidate:
                return False
            
            candidate = candidate.strip()
            words = candidate.split()
            
            # Skip if it's the extracted name
            if extracted_name and candidate.lower() == extracted_name.lower():
                return False
            
            # Structural validation: length constraints
            if len(candidate) < 3 or len(candidate) > 100:
                return False
            
            # Structural validation: check for concatenated words (no spaces in long strings)
            # Locations should have proper word spacing
            if ',' in candidate:
                parts = candidate.split(',')
                for part in parts:
                    part = part.strip()
                    # Long words without spaces are likely concatenated (e.g., "GoodexperienceinPython")
                    if len(part) > 15 and ' ' not in part:
                        return False
                    # Check for mixed case patterns that suggest concatenation
                    # (e.g., "GoodexperienceinPython" has lowercase after capital without space)
                    if len(part) > 10:
                        # Check if it has lowercase letters immediately after capital (bad pattern)
                        if re.search(r'[A-Z][a-z]{3,}[A-Z]', part):
                            return False
            
            # Structural validation: check word length (locations don't have extremely long words)
            for word in words:
                # Very long words (>20 chars) are suspicious for locations
                if len(word) > 20:
                    return False
                # Check for technical patterns: mixed case with numbers or special chars
                if re.search(r'[A-Z][a-z]+[A-Z]', word) and len(word) > 8:
                    # Pattern like "JavaScript" or "GoodExperience" - likely not a location
                    return False
            
            # Pattern-based validation: City, State format (e.g., "Atlanta, GA")
            if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}$', candidate):
                return True
            
            # Pattern-based validation: City, State ZIP (e.g., "Atlanta, GA 30309")
            if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?$', candidate):
                return True
            
            # Pattern-based validation: City, Country (must have proper format)
            if ',' in candidate:
                parts = [p.strip() for p in candidate.split(',')]
                if len(parts) == 2:
                    first_part = parts[0]
                    second_part = parts[1]
                    
                    # First part must follow location naming pattern (proper capitalization)
                    if not re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', first_part):
                        return False
                    
                    # Second part must be a known state or country abbreviation/name
                    second_lower = second_part.lower()
                    if second_lower in us_states or second_lower in countries:
                        return True
                    # Or follow proper location format (2-3 words, proper capitalization)
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}$', second_part):
                        # Additional check: second part should be short (countries/states are typically short)
                        if len(second_part) <= 20:
                            return True
                    return False
            
            # Pattern-based validation: Known state/country abbreviations or names
            candidate_lower = candidate.lower()
            if candidate_lower in us_states or candidate_lower in countries:
                return True
            
            # Pattern-based validation: Contains state abbreviation (2-letter uppercase)
            for word in words:
                # Check for 2-letter uppercase (state abbreviation)
                if len(word) == 2 and word.isupper() and word.lower() in us_states:
                    return True
            
            # Pattern-based validation: Single word locations - very strict
            if len(words) == 1:
                word = words[0]
                # Must be proper noun format (capitalized, reasonable length)
                if not re.match(r'^[A-Z][a-z]+$', word):
                    return False
                # Must be reasonable length for a city name (3-20 chars)
                if not (3 <= len(word) <= 20):
                    return False
                # Reject if it looks like a technical term (has mixed case patterns)
                if re.search(r'[a-z][A-Z]', word):
                    return False
                # Too risky to guess single word cities - reject for safety
                return False
            
            # If no pattern matches, reject (be conservative)
            return False
        
        # Only scan header section (first 10 lines) for location
        header = "\n".join(text.split("\n")[:10]).strip()
        doc = self.nlp(header)
        
        # Look for location patterns first (most reliable)
        # Use stricter patterns that require proper word boundaries
        location_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b',  # City, State (requires proper word spacing)
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s+(\d{5})',  # City, State ZIP
            # For City, Country - only match if second part is a known state/country
        ]
        
        for pattern in location_patterns:
            matches = re.finditer(pattern, header)
            for match in matches:
                candidate = match.group(0).strip()
                if is_valid_location(candidate):
                    contact.location = candidate
                    return contact
        
        # Special handling for City, Country pattern - only if second part is known
        city_country_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.finditer(city_country_pattern, header)
        for match in matches:
            candidate = match.group(0).strip()
            # Extract second part and check if it's a known country/state
            parts = candidate.split(',')
            if len(parts) == 2:
                second_part = parts[1].strip().lower()
                if second_part in us_states or second_part in countries:
                    if is_valid_location(candidate):
                        contact.location = candidate
                        return contact
        
        # Then check spaCy entities (less reliable, be more strict)
        location_ents = []
        for ent in doc.ents:
            if ent.label_ in ["GPE", "LOC"]:
                candidate = ent.text.strip()
                if is_valid_location(candidate):
                    location_ents.append(candidate)
        
        # Only use spaCy entities if we found a clearly valid location
        if location_ents:
            contact.location = location_ents[0]
        # Otherwise, leave location as None (don't guess)
        
        return contact

    def find_sections(self, text: str) -> Dict[str, str]:
        """Find and extract resume sections with improved accuracy."""
        lines = text.split('\n')
        sections = {}
        current_section = "header"
        sections[current_section] = []
        
        # Create keyword mapping
        keyword_to_section = {}
        for section, keywords in SECTION_KEYWORDS.items():
            for keyword in keywords:
                keyword_to_section[keyword.lower()] = section
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            normalized = line_stripped.lower()
            matched_section = None
            
            # Check for section headers
            for keyword, section_name in keyword_to_section.items():
                if (re.search(r'\b' + re.escape(keyword) + r'\b', normalized) and 
                    len(line_stripped) < 50 and 
                    not any(char.isdigit() for char in line_stripped[:10])):
                    matched_section = section_name
                    break
            
            if matched_section:
                current_section = matched_section
                if current_section not in sections:
                    sections[current_section] = []
                continue
            else:
                sections.setdefault(current_section, []).append(line_stripped)
        
        # Clean up sections
        for section in sections:
            content_lines = sections[section]
            # Remove empty lines from start and end
            while content_lines and not content_lines[0].strip():
                content_lines.pop(0)
            while content_lines and not content_lines[-1].strip():
                content_lines.pop()
            sections[section] = "\n".join(content_lines).strip()
        
        return sections

    def extract_skills(self, text: str, sections: Optional[Dict[str, str]] = None) -> List[str]:
        """Extract technical skills and competencies with comprehensive detection.

        `sections` can be passed in when the caller has already segmented the
        resume text, to avoid re-running section detection multiple times.
        """
        skills = set()
        text_lower = text.lower()
        # Avoid recomputing sections repeatedly inside this method
        if sections is None:
            sections = self.find_sections(text)
        
        # 1. Extract known technical skills with word boundaries
        for skill in TECH_SKILLS:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                skills.add(skill.title())
        
        # 2. Extract skills from specific sections
        skills_section = sections.get("skills", "")
        if skills_section:
            # Split by common delimiters
            skill_lines = re.split(r'[,;|\n•\-\*]', skills_section)
            for line in skill_lines:
                line = line.strip()
                if line and len(line) > 2:
                    # Check if it's a known skill
                    for skill in TECH_SKILLS:
                        if skill.lower() in line.lower():
                            skills.add(skill.title())
                    # Add the line if it looks like a skill
                    if any(keyword in line.lower() for keyword in 
                          ['programming', 'language', 'framework', 'tool', 'technology', 'platform']):
                        skills.add(line.title())
        
        # 3. Extract from experience and summary sections
        experience_text = sections.get("experience", "")
        summary_text = sections.get("professional_summary", "")
        combined_text = experience_text + " " + summary_text
        
        # Look for skill patterns in experience
        skill_context_patterns = [
            r'(?:proficient|experienced|skilled|expert|knowledgeable|familiar)\s+(?:in|with|at)?\s*([^.,\n]+)',
            r'(?:experience|expertise|skills?)\s+(?:in|with|at)?\s*([^.,\n]+)',
            r'(?:worked\s+with|used|utilized|implemented|developed)\s+([^.,\n]+)',
            r'(?:technologies?|tools?|frameworks?|languages?|platforms?):\s*([^.,\n]+)'
        ]
        
        for pattern in skill_context_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            for match in matches:
                # Split by common delimiters
                potential_skills = re.split(r'[,;|\s+and\s+|\s+&\s+]', match)
                for skill in potential_skills:
                    skill = skill.strip()
                    if skill and len(skill) > 2:
                        # Check if it's a known skill
                        for known_skill in TECH_SKILLS:
                            if known_skill.lower() in skill.lower():
                                skills.add(known_skill.title())
        
        # 4. Extract from bullet points and lists
        bullet_patterns = [
            r'[•\-\*]\s*([^.\n]+(?:python|java|javascript|react|angular|aws|azure|docker|kubernetes|sql|mongodb|salesforce|selenium|testing|automation)[^.\n]*)',
            r'[•\-\*]\s*(?:proficient|experienced|skilled|expert|knowledgeable|familiar)\s+(?:in|with|at)?\s*([^.\n]+)',
            r'[•\-\*]\s*(?:worked\s+with|used|utilized|implemented|developed)\s+([^.\n]+)'
        ]
        
        for pattern in bullet_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Split by common delimiters
                potential_skills = re.split(r'[,;|\s+and\s+|\s+&\s+]', match)
                for skill in potential_skills:
                    skill = skill.strip()
                    if skill and len(skill) > 2:
                        # Check if it's a known skill
                        for known_skill in TECH_SKILLS:
                            if known_skill.lower() in skill.lower():
                                skills.add(known_skill.title())
        
        # 5. Extract from specific technology patterns
        tech_patterns = [
            # Programming languages
            r'\b(?:Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin|Scala|R|MATLAB|Perl|Bash|PowerShell)\b',
            # Web frameworks
            r'\b(?:React|Angular|Vue|Node\.js|Express|Django|Flask|Spring|Laravel|Symfony|ASP\.NET|jQuery|Bootstrap|Sass|Less|Webpack|Babel)\b',
            # Cloud & DevOps
            r'\b(?:AWS|Azure|GCP|Docker|Kubernetes|Jenkins|Terraform|Ansible|Chef|Puppet|Git|GitHub|GitLab|Bitbucket|CI/CD|DevOps|Microservices)\b',
            # Databases
            r'\b(?:SQL|MySQL|PostgreSQL|MongoDB|Redis|Cassandra|Elasticsearch|Oracle|SQLite|MariaDB|DynamoDB|Neo4j|InfluxDB)\b',
            # Testing tools
            r'\b(?:Selenium|Cypress|Jest|Mocha|JUnit|TestNG|PyTest|Postman|JMeter|LoadRunner|Katalon|Appium|TOSCA)\b',
            # Salesforce
            r'\b(?:Salesforce|Apex|Visualforce|Lightning|Salesforce Admin|Salesforce Developer|Salesforce Architect|CRM|Marketo|HubSpot)\b',
            # Mobile
            r'\b(?:Android|iOS|React Native|Flutter|Xamarin|Ionic|Cordova|PhoneGap)\b',
            # Data Science
            r'\b(?:Pandas|NumPy|Scikit-learn|TensorFlow|PyTorch|Keras|Spark|Hadoop|Hive|Pig|Kafka|Airflow|Jupyter|Tableau|Power BI|Excel)\b',
            # Operating Systems
            r'\b(?:Linux|Windows|macOS|Unix|Ubuntu|CentOS|RedHat|Debian|Fedora)\b',
            # Methodologies
            r'\b(?:Agile|Scrum|Kanban|Waterfall|Lean|Six Sigma|ITIL|PMP|PRINCE2)\b',
            # Other technologies
            r'\b(?:API|REST|SOAP|GraphQL|JSON|XML|YAML|HTML|CSS|Nginx|Apache|Tomcat|IIS)\b'
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            skills.update(matches)
        
        # 6. Clean and deduplicate skills
        cleaned_skills = []
        seen_skills = set()  # Track normalized skills to avoid duplicates
        
        for skill in skills:
            skill = skill.strip()
            if skill and len(skill) > 1:
                # Remove common prefixes/suffixes
                skill = re.sub(r'^(proficient|experienced|skilled|expert|knowledgeable|familiar)\s+(?:in|with|at)?\s*', '', skill, flags=re.IGNORECASE)
                skill = re.sub(r'\s+(proficient|experienced|skilled|expert|knowledgeable|familiar)$', '', skill, flags=re.IGNORECASE)
                
                # Normalize the skill for comparison (lowercase, remove extra spaces, handle common variations)
                normalized_skill = re.sub(r'\s+', ' ', skill.lower().strip())
                
                # Handle common variations
                normalized_skill = re.sub(r'\bnode\.js\b', 'nodejs', normalized_skill)
                normalized_skill = re.sub(r'\bci/cd\b', 'cicd', normalized_skill)
                normalized_skill = re.sub(r'\basp\.net\b', 'aspnet', normalized_skill)
                normalized_skill = re.sub(r'\bc\+\+\b', 'cpp', normalized_skill)
                normalized_skill = re.sub(r'\bc#\b', 'csharp', normalized_skill)
                
                # Only add if we haven't seen this normalized skill before
                if normalized_skill not in seen_skills and len(normalized_skill) > 1:
                    seen_skills.add(normalized_skill)
                    # Use the original case from the first occurrence
                    cleaned_skills.append(skill)
        
        # Sort the final list
        return sorted(cleaned_skills)

    def extract_experience(self, experience_text: str) -> List[JobExperience]:
        """Extract work experience with improved parsing."""
        jobs = []
        lines = experience_text.split('\n')
        current_job = JobExperience()
        current_responsibilities = []

        def _parse_date_str(date_str: str) -> Optional[datetime]:
            """Best-effort parsing of a date string into a datetime (month-level granularity)."""
            if not date_str:
                return None
            s = date_str.strip()
            s_lower = s.lower()
            if s_lower in {"present", "current", "now"}:
                return datetime.today()

            # Try a series of common patterns
            candidates = [
                "%b %Y",      # Jan 2020
                "%B %Y",      # January 2020
                "%m/%Y",      # 01/2020
                "%m-%Y",      # 01-2020
                "%Y/%m/%d",   # 2020/01/15
                "%Y-%m-%d",   # 2020-01-15
                "%m/%d/%Y",   # 01/15/2020
                "%d/%m/%Y",   # 15/01/2020
                "%Y",         # 2020 (assume Jan 1st)
            ]
            for fmt in candidates:
                try:
                    dt = datetime.strptime(s, fmt)
                    # Normalize to first of month to keep month-level comparisons simple
                    return datetime(dt.year, dt.month, 1)
                except Exception:
                    continue
            return None

        def _format_duration(start: Optional[datetime], end: Optional[datetime]) -> Optional[str]:
            """Return a human-readable duration between two datetimes."""
            if not start or not end:
                return None
            if end < start:
                return None
            total_months = (end.year - start.year) * 12 + (end.month - start.month)
            if total_months <= 0:
                return None
            years, months = divmod(total_months, 12)
            parts = []
            if years:
                parts.append(f"{years} year{'s' if years != 1 else ''}")
            if months:
                parts.append(f"{months} month{'s' if months != 1 else ''}")
            return " ".join(parts) if parts else None

        def _finalize_job(job: JobExperience):
            """Compute derived fields like duration before appending."""
            if job.start_date:
                start_dt = _parse_date_str(job.start_date)
            else:
                start_dt = None
            if job.end_date:
                end_dt = _parse_date_str(job.end_date)
            else:
                end_dt = None
            duration = _format_duration(start_dt, end_dt)
            if duration:
                job.duration = duration
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # Check for date patterns
            date_match = DATE_RANGE_REGEX.search(line_stripped)
            
            if date_match:
                # Save previous job if exists
                if current_job.title or current_job.company:
                    current_job.responsibilities = current_responsibilities
                    _finalize_job(current_job)
                    jobs.append(current_job)
                
                # Start new job
                current_job = JobExperience()
                current_responsibilities = []
                
                # Extract dates
                date_text = date_match.group(0)
                dates = re.findall(r'(?i)(?:' + '|'.join(DATE_PATTERNS) + r'|present|current)', date_text)
                if len(dates) >= 1:
                    current_job.start_date = dates[0]
                if len(dates) >= 2:
                    current_job.end_date = dates[1]
                
                # Look for job title and company in previous lines
                for j in range(max(0, i-3), i):
                    prev_line = lines[j].strip()
                    if not prev_line:
                        continue
                    
                    # Check if line contains job title keywords
                    if any(keyword in prev_line.lower() for keyword in JOB_TITLE_KEYWORDS):
                        if not current_job.title:
                            current_job.title = prev_line
                        elif not current_job.company:
                            current_job.company = prev_line
                    # Check for company indicators
                    elif re.search(r'\b(?:Inc|LLC|Corp|Co|Ltd|Company|Corporation)\b', prev_line, re.IGNORECASE):
                        if not current_job.company:
                            current_job.company = prev_line
                        elif not current_job.title:
                            current_job.title = prev_line
                    else:
                        if not current_job.title and len(prev_line) < 100:
                            current_job.title = prev_line
                        elif not current_job.company and len(prev_line) < 100:
                            current_job.company = prev_line

                # Look for a location line in the few lines following the date line (e.g., "Fort Collins, CO")
                if not current_job.location:
                    for k in range(i + 1, min(len(lines), i + 5)):
                        loc_line = lines[k].strip()
                        if not loc_line:
                            continue
                        # Simple, conservative pattern: City, ST
                        if re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}\b', loc_line):
                            current_job.location = loc_line
                            break
            
            elif current_job.title or current_job.company:
                # This is likely a responsibility or achievement
                current_responsibilities.append(line_stripped)
        
        # Add the last job
        if current_job.title or current_job.company:
            current_job.responsibilities = current_responsibilities
            _finalize_job(current_job)
            jobs.append(current_job)
        
        return jobs

    def extract_education(self, education_text: str) -> List[Education]:
        """Extract education information."""
        education_list = []
        lines = education_text.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or len(line_stripped) < 10:
                continue
            
            # Look for degree patterns
            degree_patterns = [
                r'\b(?:Bachelor|Master|PhD|Doctorate|Associate|Certificate|Diploma)\b',
                r'\b(?:B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|Ph\.?D\.?)\b'
            ]
            
            if any(re.search(pattern, line_stripped, re.IGNORECASE) for pattern in degree_patterns):
                education = Education()
                
                # Extract degree
                for pattern in degree_patterns:
                    match = re.search(pattern, line_stripped, re.IGNORECASE)
                    if match:
                        education.degree = match.group(0)
                        break
                
                # Extract institution (usually contains "University", "College", "Institute")
                if re.search(r'\b(?:University|College|Institute|School)\b', line_stripped, re.IGNORECASE):
                    education.institution = line_stripped
                else:
                    education.institution = line_stripped
                
                education_list.append(education)
        
        return education_list

    def calculate_confidence_score(self, parsed_resume: ParsedResume) -> float:
        """Calculate confidence score based on extracted information."""
        score = 0.0
        max_score = 10.0
        
        # Contact information (3 points)
        if parsed_resume.contact.name:
            score += 1.0
        if parsed_resume.contact.email:
            score += 1.0
        if parsed_resume.contact.phone:
            score += 1.0
        
        # Professional summary (1 point)
        if parsed_resume.professional_summary:
            score += 1.0
        
        # Experience (3 points)
        if parsed_resume.experience:
            score += min(3.0, len(parsed_resume.experience) * 0.5)
        
        # Education (1 point)
        if parsed_resume.education:
            score += 1.0
        
        # Skills (1 point)
        if parsed_resume.skills:
            score += 1.0
        
        # Certifications (1 point)
        if parsed_resume.certifications:
            score += 1.0
        
        return min(1.0, score / max_score)

    def parse_resume(self, file_path: str) -> ParsedResume:
        """Parse resume from file with comprehensive extraction."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Extract text based on file type
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            text = self.extract_text_from_pdf(file_path)
        elif ext == ".docx":
            text = self.extract_text_from_docx(file_path)
        else:
            raise ValueError("Unsupported file type. Only PDF and DOCX are supported.")
        
        if not text:
            logger.warning(f"No text extracted from {file_path}")
            return ParsedResume(file_path=file_path, contact=ContactInfo())
        
        # Extract sections
        sections = self.find_sections(text)
        
        # Extract contact information
        contact = self.extract_contact_info(text)
        
        # Extract other information
        professional_summary = sections.get("professional_summary")
        experience = self.extract_experience(sections.get("experience", ""))
        education = self.extract_education(sections.get("education", ""))
        # Pass precomputed sections into extract_skills to avoid redundant work
        skills = self.extract_skills(text, sections)
        # Extract certifications from multiple sources
        certifications = []
        
        # From certifications section
        cert_section = sections.get("certifications", "")
        if cert_section:
            for line in cert_section.split('\n'):
                line = line.strip()
                if line and any(word in line.lower() for word in 
                               ["certified", "certificate", "certification", "license", "credential"]):
                    certifications.append(line)
        
        # From entire text (look for certification patterns)
        cert_patterns = [
            r'\b(?:AWS|Azure|Google Cloud|Salesforce|TOSCA|PMP|ITIL|CISSP|CISA|CISM)\s+(?:Certified|Certification|Certificate)\b',
            r'\b(?:Certified|Certification|Certificate)\s+(?:in|for)?\s*(?:AWS|Azure|Google Cloud|Salesforce|TOSCA|PMP|ITIL|CISSP|CISA|CISM)\b',
            r'\b(?:AWS|Azure|Google Cloud|Salesforce|TOSCA|PMP|ITIL|CISSP|CISA|CISM)\s+\w+\s+(?:Certified|Certification|Certificate)\b'
        ]
        
        for pattern in cert_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            certifications.extend(matches)
        
        # Remove duplicates and clean up
        certifications = list(set([cert.strip() for cert in certifications if cert.strip()]))
        
        # Create parsed resume object
        parsed_resume = ParsedResume(
            file_path=file_path,
            contact=contact,
            professional_summary=professional_summary,
            experience=experience,
            education=education,
            skills=skills,
            certifications=certifications,
            raw_text=text
        )
        
        # Calculate confidence score
        parsed_resume.confidence_score = self.calculate_confidence_score(parsed_resume)
        
        return parsed_resume

    def to_dict(self, parsed_resume: ParsedResume) -> Dict[str, Any]:
        """Convert ParsedResume to dictionary for JSON serialization."""
        result = asdict(parsed_resume)
        return result

def main():
    """Main function for testing the parser."""
    parser = ResumeParser()
    
    # Test with the provided resume
    resume_path = "Anusha.docx"
    
    try:
        parsed_data = parser.parse_resume(resume_path)
        
        print("=" * 60)
        print("PARSED RESUME DATA")
        print("=" * 60)
        print(f"File: {parsed_data.file_path}")
        print(f"Confidence Score: {parsed_data.confidence_score:.2f}")
        print("=" * 60)
        
        print(f"\nContact Information:")
        print(f"  Name: {parsed_data.contact.name}")
        print(f"  Email: {parsed_data.contact.email}")
        print(f"  Phone: {parsed_data.contact.phone}")
        print(f"  Location: {parsed_data.contact.location}")
        
        print(f"\nProfessional Summary:")
        print(f"  {parsed_data.professional_summary}")
        
        print(f"\nExperience ({len(parsed_data.experience)} positions):")
        for i, job in enumerate(parsed_data.experience, 1):
            print(f"  {i}. {job.title} at {job.company}")
            print(f"     Dates: {job.start_date} - {job.end_date}")
            if job.responsibilities:
                print(f"     Key Responsibilities:")
                for resp in job.responsibilities[:3]:  # Show first 3
                    print(f"       - {resp}")
            print()
        
        print(f"\nEducation ({len(parsed_data.education)} entries):")
        for edu in parsed_data.education:
            print(f"  - {edu.degree} from {edu.institution}")
        
        print(f"\nSkills ({len(parsed_data.skills)} skills):")
        if parsed_data.skills:
            # Group skills by category for better display
            skill_categories = {
                'Programming Languages': [],
                'Web Technologies': [],
                'Cloud & DevOps': [],
                'Databases': [],
                'Testing & QA': [],
                'Salesforce & CRM': [],
                'Mobile Development': [],
                'Data Science': [],
                'Operating Systems': [],
                'Methodologies': [],
                'Other Technologies': []
            }
            
            # Categorize skills (remove duplicates first)
            unique_skills = []
            seen_skills = set()
            for skill in parsed_data.skills:
                normalized = skill.lower().strip()
                if normalized not in seen_skills:
                    seen_skills.add(normalized)
                    unique_skills.append(skill)
            
            for skill in unique_skills:
                skill_lower = skill.lower()
                categorized = False
                
                if any(tech in skill_lower for tech in ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'php', 'ruby', 'go', 'rust', 'swift', 'kotlin', 'scala', 'r', 'matlab', 'perl', 'bash', 'powershell']):
                    skill_categories['Programming Languages'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring', 'laravel', 'symfony', 'asp.net', 'jquery', 'bootstrap', 'sass', 'less', 'webpack', 'babel']):
                    skill_categories['Web Technologies'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'terraform', 'ansible', 'chef', 'puppet', 'git', 'github', 'gitlab', 'bitbucket', 'ci/cd', 'devops', 'microservices']):
                    skill_categories['Cloud & DevOps'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'cassandra', 'elasticsearch', 'oracle', 'sqlite', 'mariadb', 'dynamodb', 'neo4j', 'influxdb']):
                    skill_categories['Databases'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['selenium', 'cypress', 'jest', 'mocha', 'junit', 'testng', 'pytest', 'postman', 'jmeter', 'loadrunner', 'katalon', 'appium', 'testing', 'qa', 'automation', 'tosca']):
                    skill_categories['Testing & QA'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['salesforce', 'apex', 'visualforce', 'lightning', 'crm', 'marketo', 'hubspot']):
                    skill_categories['Salesforce & CRM'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['android', 'ios', 'react native', 'flutter', 'xamarin', 'ionic', 'cordova', 'phonegap']):
                    skill_categories['Mobile Development'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch', 'keras', 'spark', 'hadoop', 'hive', 'pig', 'kafka', 'airflow', 'jupyter', 'tableau', 'power bi', 'excel']):
                    skill_categories['Data Science'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['linux', 'windows', 'macos', 'unix', 'ubuntu', 'centos', 'redhat', 'debian', 'fedora']):
                    skill_categories['Operating Systems'].append(skill)
                    categorized = True
                elif any(tech in skill_lower for tech in ['agile', 'scrum', 'kanban', 'waterfall', 'lean', 'six sigma', 'itil', 'pmp', 'prince2']):
                    skill_categories['Methodologies'].append(skill)
                    categorized = True
                
                if not categorized:
                    skill_categories['Other Technologies'].append(skill)
            
            # Display categorized skills
            for category, skill_list in skill_categories.items():
                if skill_list:
                    print(f"  {category}: {', '.join(skill_list[:5])}{'...' if len(skill_list) > 5 else ''}")
        else:
            print("  No skills detected")
        
        print(f"\nCertifications ({len(parsed_data.certifications)} certifications):")
        for cert in parsed_data.certifications:
            print(f"  - {cert}")
        
        print(f"\nConfidence Score: {parsed_data.confidence_score:.2f}")
        
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
