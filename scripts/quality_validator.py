#!/usr/bin/env python3
"""
Content Quality Validator
Provides automated quality assessment for generated content.
"""

import json
import logging
import re
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

import openai
from textstat import flesch_reading_ease, flesch_kincaid_grade, automated_readability_index

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Container for content quality assessment results."""
    overall_score: float  # 1-10 scale
    readability_score: float
    grammar_score: float
    engagement_score: float
    brand_consistency_score: float
    factual_accuracy_score: float
    length_optimization_score: float
    
    # Detailed feedback
    issues: List[str]
    suggestions: List[str]
    strengths: List[str]
    
    # Metrics
    word_count: int
    sentence_count: int
    paragraph_count: int
    reading_level: str
    
    # Flags
    requires_review: bool
    auto_approve: bool


class ContentQualityValidator:
    """Automated content quality assessment and validation system."""
    
    def __init__(self, config_path: str = "config/api-keys.json", quality_rules_path: str = "config/quality_rules.json"):
        """Initialize the quality validator."""
        self.config_path = Path(config_path)
        self.quality_rules_path = Path(quality_rules_path)
        
        self.config = self._load_config()
        self.quality_rules = self._load_quality_rules()
        
        # Initialize OpenAI client for advanced analysis
        self.openai_client = openai.OpenAI(api_key=self.config["openai"]["api_key"])
        
        logger.info("Content Quality Validator initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load API configuration."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
    
    def _load_quality_rules(self) -> Dict[str, Any]:
        """Load quality assessment rules."""
        try:
            with open(self.quality_rules_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Quality rules file not found: {self.quality_rules_path}")
            return self._get_default_quality_rules()
    
    def _get_default_quality_rules(self) -> Dict[str, Any]:
        """Get default quality assessment rules."""
        return {
            "readability": {
                "min_flesch_score": 60,  # Fairly easy to read
                "max_grade_level": 10,   # 10th grade reading level
                "preferred_sentence_length": {"min": 10, "max": 25}
            },
            "length_requirements": {
                "blog_post": {"min": 800, "max": 2500, "optimal": 1500},
                "twitter_thread": {"min": 200, "max": 800, "optimal": 400},
                "newsletter_summary": {"min": 150, "max": 300, "optimal": 200},
                "seo_summary": {"min": 100, "max": 500, "optimal": 250}
            },
            "engagement_factors": {
                "question_ratio": {"min": 0.02, "max": 0.1},  # 2-10% questions
                "emoji_ratio": {"min": 0.001, "max": 0.05},   # 0.1-5% emojis
                "call_to_action": True,
                "personal_pronouns": {"min": 0.01, "max": 0.08}
            },
            "quality_thresholds": {
                "auto_approve": 8.0,
                "requires_review": 6.0,
                "reject": 4.0
            },
            "prohibited_patterns": [
                r"click here",
                r"lorem ipsum",
                r"\[placeholder\]",
                r"TODO:",
                r"FIXME:"
            ],
            "required_elements": {
                "blog_post": ["introduction", "conclusion", "headings"],
                "twitter_thread": ["hook", "call_to_action"],
                "newsletter_summary": ["key_takeaways", "action_items"],
                "seo_summary": ["keywords", "meta_description"]
            }
        }
    
    async def validate_content(self, content: str, content_type: str, original_url: str = "") -> QualityScore:
        """Perform comprehensive quality validation on content."""
        logger.info(f"Validating {content_type} content ({len(content)} characters)")
        
        # Basic metrics
        word_count = len(content.split())
        sentence_count = len(re.findall(r'[.!?]+', content))
        paragraph_count = len([p for p in content.split('\n\n') if p.strip()])
        
        # Run all quality checks in parallel
        quality_tasks = [
            self._assess_readability(content),
            self._assess_grammar_and_style(content),
            self._assess_engagement_factors(content, content_type),
            self._assess_length_optimization(content, content_type),
            self._assess_brand_consistency(content),
            self._assess_factual_accuracy(content, original_url)
        ]
        
        results = await asyncio.gather(*quality_tasks, return_exceptions=True)
        
        # Process results
        readability_score = results[0] if not isinstance(results[0], Exception) else 5.0
        grammar_score = results[1] if not isinstance(results[1], Exception) else 5.0
        engagement_score = results[2] if not isinstance(results[2], Exception) else 5.0
        length_score = results[3] if not isinstance(results[3], Exception) else 5.0
        brand_score = results[4] if not isinstance(results[4], Exception) else 7.0
        factual_score = results[5] if not isinstance(results[5], Exception) else 7.0
        
        # Calculate overall score (weighted average)
        weights = {
            'readability': 0.20,
            'grammar': 0.25,
            'engagement': 0.20,
            'length': 0.10,
            'brand': 0.15,
            'factual': 0.10
        }
        
        overall_score = (
            readability_score * weights['readability'] +
            grammar_score * weights['grammar'] +
            engagement_score * weights['engagement'] +
            length_score * weights['length'] +
            brand_score * weights['brand'] +
            factual_score * weights['factual']
        )
        
        # Collect issues and suggestions
        issues, suggestions, strengths = await self._generate_feedback(
            content, content_type, {
                'readability': readability_score,
                'grammar': grammar_score,
                'engagement': engagement_score,
                'length': length_score,
                'brand': brand_score,
                'factual': factual_score
            }
        )
        
        # Determine reading level
        try:
            grade_level = flesch_kincaid_grade(content)
            if grade_level <= 6:
                reading_level = "Elementary"
            elif grade_level <= 9:
                reading_level = "Middle School"
            elif grade_level <= 12:
                reading_level = "High School"
            else:
                reading_level = "College"
        except:
            reading_level = "Unknown"
        
        # Quality flags
        thresholds = self.quality_rules["quality_thresholds"]
        auto_approve = overall_score >= thresholds["auto_approve"]
        requires_review = thresholds["requires_review"] <= overall_score < thresholds["auto_approve"]
        
        return QualityScore(
            overall_score=round(overall_score, 1),
            readability_score=round(readability_score, 1),
            grammar_score=round(grammar_score, 1),
            engagement_score=round(engagement_score, 1),
            brand_consistency_score=round(brand_score, 1),
            factual_accuracy_score=round(factual_score, 1),
            length_optimization_score=round(length_score, 1),
            issues=issues,
            suggestions=suggestions,
            strengths=strengths,
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            reading_level=reading_level,
            requires_review=requires_review,
            auto_approve=auto_approve
        )
    
    async def _assess_readability(self, content: str) -> float:
        """Assess content readability using multiple metrics."""
        try:
            # Flesch Reading Ease (0-100, higher is easier)
            flesch_score = flesch_reading_ease(content)
            
            # Flesch-Kincaid Grade Level
            grade_level = flesch_kincaid_grade(content)
            
            # Automated Readability Index
            ari_score = automated_readability_index(content)
            
            # Convert to 1-10 scale
            readability_rules = self.quality_rules["readability"]
            
            # Flesch score assessment (60+ is good)
            flesch_normalized = min(10, max(1, (flesch_score - 30) / 7))
            
            # Grade level assessment (10th grade or below is good)
            grade_normalized = min(10, max(1, 11 - grade_level))
            
            # Average sentence length check
            sentences = re.findall(r'[.!?]+', content)
            if sentences:
                avg_sentence_length = len(content.split()) / len(sentences)
                sentence_score = 10 if 10 <= avg_sentence_length <= 25 else max(1, 10 - abs(avg_sentence_length - 17.5) / 2)
            else:
                sentence_score = 5
            
            # Weighted average
            readability_score = (flesch_normalized * 0.4 + grade_normalized * 0.4 + sentence_score * 0.2)
            
            return min(10, max(1, readability_score))
            
        except Exception as e:
            logger.error(f"Error assessing readability: {e}")
            return 5.0
    
    async def _assess_grammar_and_style(self, content: str) -> float:
        """Assess grammar and writing style using AI."""
        try:
            prompt = f"""
            Analyze the following content for grammar, style, and writing quality. 
            Rate it on a scale of 1-10 where:
            - 10: Excellent grammar, clear style, professional writing
            - 7-9: Good quality with minor issues
            - 4-6: Average quality with some issues
            - 1-3: Poor quality with major issues
            
            Content to analyze:
            {content[:1500]}...
            
            Provide only a numerical score (1-10) and brief reasoning.
            """
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional editor and writing quality assessor."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            result = response.choices[0].message.content.strip()
            
            # Extract numerical score
            score_match = re.search(r'(\d+(?:\.\d+)?)', result)
            if score_match:
                score = float(score_match.group(1))
                return min(10, max(1, score))
            else:
                return 7.0  # Default if no score found
                
        except Exception as e:
            logger.error(f"Error assessing grammar: {e}")
            return 7.0
    
    async def _assess_engagement_factors(self, content: str, content_type: str) -> float:
        """Assess content engagement potential."""
        try:
            engagement_rules = self.quality_rules["engagement_factors"]
            score_components = []
            
            # Question ratio
            questions = len(re.findall(r'\?', content))
            total_sentences = len(re.findall(r'[.!?]+', content))
            question_ratio = questions / max(total_sentences, 1)
            
            if engagement_rules["question_ratio"]["min"] <= question_ratio <= engagement_rules["question_ratio"]["max"]:
                score_components.append(10)
            else:
                score_components.append(max(1, 10 - abs(question_ratio - 0.06) * 100))
            
            # Emoji usage (for appropriate content types)
            if content_type in ["blog_post", "twitter_thread"]:
                emojis = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', content))
                emoji_ratio = emojis / max(len(content.split()), 1)
                
                if engagement_rules["emoji_ratio"]["min"] <= emoji_ratio <= engagement_rules["emoji_ratio"]["max"]:
                    score_components.append(10)
                else:
                    score_components.append(max(1, 10 - abs(emoji_ratio - 0.025) * 200))
            else:
                score_components.append(8)  # Neutral for non-emoji content
            
            # Call to action presence
            cta_patterns = [
                r'click here', r'learn more', r'read more', r'subscribe', r'follow',
                r'share', r'comment', r'like', r'try', r'get started', r'download'
            ]
            has_cta = any(re.search(pattern, content.lower()) for pattern in cta_patterns)
            score_components.append(10 if has_cta else 5)
            
            # Personal pronouns (engagement indicator)
            personal_pronouns = len(re.findall(r'\b(you|your|we|our|us|I|my|me)\b', content, re.IGNORECASE))
            pronoun_ratio = personal_pronouns / max(len(content.split()), 1)
            
            if engagement_rules["personal_pronouns"]["min"] <= pronoun_ratio <= engagement_rules["personal_pronouns"]["max"]:
                score_components.append(10)
            else:
                score_components.append(max(1, 10 - abs(pronoun_ratio - 0.045) * 100))
            
            return sum(score_components) / len(score_components)
            
        except Exception as e:
            logger.error(f"Error assessing engagement: {e}")
            return 6.0
    
    async def _assess_length_optimization(self, content: str, content_type: str) -> float:
        """Assess if content length is optimized for the content type."""
        try:
            word_count = len(content.split())
            length_rules = self.quality_rules["length_requirements"].get(content_type, {})
            
            if not length_rules:
                return 7.0  # Default if no rules for content type
            
            min_length = length_rules.get("min", 0)
            max_length = length_rules.get("max", 10000)
            optimal_length = length_rules.get("optimal", (min_length + max_length) / 2)
            
            if min_length <= word_count <= max_length:
                # Calculate how close to optimal
                distance_from_optimal = abs(word_count - optimal_length) / optimal_length
                score = max(7, 10 - (distance_from_optimal * 10))
            else:
                # Penalty for being outside range
                if word_count < min_length:
                    score = max(1, 5 - (min_length - word_count) / min_length * 5)
                else:
                    score = max(1, 5 - (word_count - max_length) / max_length * 5)
            
            return min(10, max(1, score))
            
        except Exception as e:
            logger.error(f"Error assessing length: {e}")
            return 7.0
    
    async def _assess_brand_consistency(self, content: str) -> float:
        """Assess brand voice and consistency (placeholder for future brand profile integration)."""
        try:
            # This is a placeholder implementation
            # In a real scenario, this would check against brand guidelines
            
            # Basic checks for professional tone
            score = 7.0  # Default baseline
            
            # Check for prohibited patterns
            prohibited = self.quality_rules.get("prohibited_patterns", [])
            for pattern in prohibited:
                if re.search(pattern, content, re.IGNORECASE):
                    score -= 2
            
            # Check for consistent tone (basic implementation)
            formal_indicators = len(re.findall(r'\b(therefore|furthermore|consequently|moreover)\b', content, re.IGNORECASE))
            casual_indicators = len(re.findall(r'\b(awesome|cool|amazing|wow|hey)\b', content, re.IGNORECASE))
            
            # Penalize mixed formal/casual tone
            if formal_indicators > 0 and casual_indicators > 0:
                score -= 1
            
            return min(10, max(1, score))
            
        except Exception as e:
            logger.error(f"Error assessing brand consistency: {e}")
            return 7.0
    
    async def _assess_factual_accuracy(self, content: str, original_url: str = "") -> float:
        """Assess potential factual accuracy issues (basic implementation)."""
        try:
            # This is a basic implementation
            # Advanced implementation would use fact-checking APIs
            
            score = 7.0  # Default baseline
            
            # Check for absolute statements that might be inaccurate
            absolute_patterns = [
                r'\ball\b.*\balways\b', r'\bnever\b.*\ball\b', r'\beveryone\b.*\bknows\b',
                r'\bguaranteed\b', r'\b100%\b.*\bsure\b'
            ]
            
            for pattern in absolute_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    score -= 0.5
            
            # Check for specific claims that need verification
            claim_patterns = [
                r'\bstudies show\b', r'\bresearch proves\b', r'\bexperts say\b',
                r'\bstatistics show\b', r'\bdata reveals\b'
            ]
            
            claims_count = sum(1 for pattern in claim_patterns if re.search(pattern, content, re.IGNORECASE))
            
            # If many claims but no source URL, reduce score
            if claims_count > 2 and not original_url:
                score -= 1
            
            return min(10, max(1, score))
            
        except Exception as e:
            logger.error(f"Error assessing factual accuracy: {e}")
            return 7.0
    
    async def _generate_feedback(self, content: str, content_type: str, scores: Dict[str, float]) -> Tuple[List[str], List[str], List[str]]:
        """Generate detailed feedback based on quality scores."""
        issues = []
        suggestions = []
        strengths = []
        
        # Readability feedback
        if scores['readability'] < 6:
            issues.append("Content may be difficult to read")
            suggestions.append("Use shorter sentences and simpler vocabulary")
        elif scores['readability'] > 8:
            strengths.append("Excellent readability and clarity")
        
        # Grammar feedback
        if scores['grammar'] < 6:
            issues.append("Grammar and style issues detected")
            suggestions.append("Review for grammar errors and improve sentence structure")
        elif scores['grammar'] > 8:
            strengths.append("High-quality writing and grammar")
        
        # Engagement feedback
        if scores['engagement'] < 6:
            issues.append("Low engagement potential")
            suggestions.append("Add more questions, calls-to-action, or personal touches")
        elif scores['engagement'] > 8:
            strengths.append("Strong engagement elements")
        
        # Length feedback
        if scores['length'] < 6:
            length_rules = self.quality_rules["length_requirements"].get(content_type, {})
            if length_rules:
                optimal = length_rules.get("optimal", 1000)
                current = len(content.split())
                if current < length_rules.get("min", 0):
                    issues.append(f"Content too short ({current} words)")
                    suggestions.append(f"Expand content to at least {length_rules['min']} words")
                elif current > length_rules.get("max", 10000):
                    issues.append(f"Content too long ({current} words)")
                    suggestions.append(f"Reduce content to under {length_rules['max']} words")
        
        # Brand consistency feedback
        if scores['brand'] < 6:
            issues.append("Brand consistency concerns")
            suggestions.append("Review content against brand guidelines")
        
        # Factual accuracy feedback
        if scores['factual'] < 6:
            issues.append("Potential factual accuracy concerns")
            suggestions.append("Verify claims and add credible sources")
        
        return issues, suggestions, strengths


async def main():
    """Test the quality validator."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python quality_validator.py <content_file>")
        sys.exit(1)
    
    content_file = sys.argv[1]
    content_type = sys.argv[2] if len(sys.argv) > 2 else "blog_post"
    
    try:
        with open(content_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        validator = ContentQualityValidator()
        quality_score = await validator.validate_content(content, content_type)
        
        print(f"\n=== Quality Assessment Results ===")
        print(f"Overall Score: {quality_score.overall_score}/10")
        print(f"Auto-approve: {quality_score.auto_approve}")
        print(f"Requires Review: {quality_score.requires_review}")
        
        print(f"\n=== Detailed Scores ===")
        print(f"Readability: {quality_score.readability_score}/10")
        print(f"Grammar: {quality_score.grammar_score}/10")
        print(f"Engagement: {quality_score.engagement_score}/10")
        print(f"Length: {quality_score.length_optimization_score}/10")
        print(f"Brand Consistency: {quality_score.brand_consistency_score}/10")
        print(f"Factual Accuracy: {quality_score.factual_accuracy_score}/10")
        
        print(f"\n=== Content Metrics ===")
        print(f"Word Count: {quality_score.word_count}")
        print(f"Reading Level: {quality_score.reading_level}")
        
        if quality_score.issues:
            print(f"\n=== Issues ===")
            for issue in quality_score.issues:
                print(f"• {issue}")
        
        if quality_score.suggestions:
            print(f"\n=== Suggestions ===")
            for suggestion in quality_score.suggestions:
                print(f"• {suggestion}")
        
        if quality_score.strengths:
            print(f"\n=== Strengths ===")
            for strength in quality_score.strengths:
                print(f"• {strength}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
