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
        """Extract text from DOCX with improved error handling."""
        try:
            doc = docx.Document(path)
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)
            return "\n".join(full_text).strip()
        except Exception as e:
            logger.error(f"Error reading DOCX {path}: {e}")
            return ""

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
        
        # Extract name using spaCy NER
        doc = nlp(text[:500])  # Only check first 500 chars for name
        for ent in doc.ents:
            if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                contact.name = ent.text.strip()
                break
        
        # Fallback name extraction from email
        if not contact.name and contact.email:
            name_candidate = contact.email.split('@')[0]
            name_candidate = re.sub(r'[._-]', ' ', name_candidate).title()
            if len(name_candidate.split()) >= 2:
                contact.name = name_candidate
        
        # Extract location
        location_ents = [ent for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]
        if location_ents:
            contact.location = location_ents[0].text
        
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

    def extract_skills(self, text: str) -> List[str]:
        """Extract technical skills and competencies with comprehensive detection."""
        skills = set()
        text_lower = text.lower()
        
        # 1. Extract known technical skills with word boundaries
        for skill in TECH_SKILLS:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                skills.add(skill.title())
        
        # 2. Extract skills from specific sections
        skills_section = self.find_sections(text).get("skills", "")
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
        experience_text = self.find_sections(text).get("experience", "")
        summary_text = self.find_sections(text).get("professional_summary", "")
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
            
            elif current_job.title or current_job.company:
                # This is likely a responsibility or achievement
                current_responsibilities.append(line_stripped)
        
        # Add the last job
        if current_job.title or current_job.company:
            current_job.responsibilities = current_responsibilities
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
        skills = self.extract_skills(text)
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
