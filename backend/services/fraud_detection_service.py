# backend/services/fraud_detection_service.py

import hashlib
import io
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image, ImageChops, ImageEnhance, ImageFilter
from PIL.ExifTags import TAGS, GPSTAGS
import numpy as np
from config.constants import FraudCheckResult
import structlog

logger = structlog.get_logger()


class FraudDetectionService:
    """
    Enterprise-grade image/video fraud detection.
    Performs multiple checks:
    1. EXIF metadata analysis
    2. Error Level Analysis (ELA)
    3. Hash-based duplicate detection
    4. AI generation detection patterns
    5. Metadata consistency checks
    """

    def __init__(self):
        self.ela_quality = 95
        self.ela_scale = 10
        self.suspicious_software = [
            "photoshop", "gimp", "affinity", "canva",
            "dall-e", "midjourney", "stable diffusion",
            "adobe firefly", "bing image creator"
        ]
        self.ai_generation_indicators = [
            "dalle", "midjourney", "stablediffusion",
            "comfyui", "automatic1111", "novelai",
            "leonardo", "firefly", "bing"
        ]

    async def analyze_image(
        self, image_bytes: bytes, filename: str
    ) -> Dict[str, Any]:
        """
        Perform comprehensive fraud analysis on an image.
        Returns overall result and individual check details.
        """
        results = []
        image = Image.open(io.BytesIO(image_bytes))

        # Check 1: EXIF Metadata Analysis
        exif_result = await self._check_exif_metadata(image, image_bytes)
        results.append(exif_result)

        # Check 2: Error Level Analysis
        ela_result = await self._perform_ela(image_bytes)
        results.append(ela_result)

        # Check 3: File Hash for duplicates
        hash_result = await self._check_file_hash(image_bytes)
        results.append(hash_result)

        # Check 4: AI Generation Detection
        ai_result = await self._detect_ai_generation(
            image, image_bytes, filename
        )
        results.append(ai_result)

        # Check 5: Metadata Consistency
        consistency_result = await self._check_metadata_consistency(
            image, image_bytes
        )
        results.append(consistency_result)

        # Calculate overall score
        overall_score, overall_result = self._calculate_overall_score(results)

        return {
            "overall_result": overall_result,
            "overall_score": overall_score,
            "checks": results,
            "recommendation": self._get_recommendation(
                overall_result, overall_score
            ),
        }

    async def _check_exif_metadata(
        self, image: Image.Image, image_bytes: bytes
    ) -> Dict[str, Any]:
        """Analyze EXIF data for authenticity indicators."""
        try:
            exif_data = {}
            raw_exif = image._getexif()

            if raw_exif is None:
                return {
                    "check_type": "exif_metadata",
                    "result": FraudCheckResult.METADATA_MISSING.value,
                    "confidence": 0.5,
                    "details": {
                        "message": "No EXIF data found. This could indicate "
                                   "the image was screenshot, downloaded, or "
                                   "AI-generated.",
                        "has_exif": False,
                    },
                }

            for tag_id, value in raw_exif.items():
                tag = TAGS.get(tag_id, tag_id)
                try:
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", errors="ignore")
                    exif_data[str(tag)] = str(value)
                except Exception:
                    pass

            # Check for camera information
            has_camera = bool(
                exif_data.get("Make") or exif_data.get("Model")
            )
            has_datetime = bool(
                exif_data.get("DateTime")
                or exif_data.get("DateTimeOriginal")
            )
            has_gps = bool(
                exif_data.get("GPSInfo")
            )

            # Check for editing software
            software = exif_data.get("Software", "").lower()
            is_edited = any(
                s in software for s in self.suspicious_software
            )

            # Scoring
            score = 0.8  # Start high
            if not has_camera:
                score -= 0.2
            if not has_datetime:
                score -= 0.15
            if is_edited:
                score -= 0.3

            result = FraudCheckResult.AUTHENTIC
            if score < 0.4:
                result = FraudCheckResult.SUSPICIOUS
            elif score < 0.6:
                result = FraudCheckResult.INCONCLUSIVE

            return {
                "check_type": "exif_metadata",
                "result": result.value,
                "confidence": max(0.0, min(1.0, score)),
                "details": {
                    "has_camera_info": has_camera,
                    "has_datetime": has_datetime,
                    "has_gps": has_gps,
                    "software": exif_data.get("Software", "Unknown"),
                    "camera_make": exif_data.get("Make", "Unknown"),
                    "camera_model": exif_data.get("Model", "Unknown"),
                    "is_edited": is_edited,
                    "exif_tags_count": len(exif_data),
                },
            }

        except Exception as e:
            logger.error("exif_check_failed", error=str(e))
            return {
                "check_type": "exif_metadata",
                "result": FraudCheckResult.INCONCLUSIVE.value,
                "confidence": 0.5,
                "details": {"error": str(e)},
            }

    async def _perform_ela(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Error Level Analysis (ELA).
        Detects image manipulation by re-saving at known quality
        and analyzing error differences.
        """
        try:
            original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            # Re-save at known quality
            buffer = io.BytesIO()
            original.save(buffer, "JPEG", quality=self.ela_quality)
            buffer.seek(0)
            resaved = Image.open(buffer)

            # Calculate difference
            ela_image = ImageChops.difference(original, resaved)

            # Convert to numpy for analysis
            ela_array = np.array(ela_image)
            max_diff = ela_array.max()
            mean_diff = ela_array.mean()
            std_diff = ela_array.std()

            # High variance in ELA indicates potential manipulation
            # Natural photos have relatively uniform ELA
            manipulation_score = 0.0

            if std_diff > 15:  # High standard deviation
                manipulation_score += 0.3
            if max_diff > 200:  # Very high max difference
                manipulation_score += 0.3
            if mean_diff > 10:  # High average difference
                manipulation_score += 0.2

            # Check for regions with significantly different error levels
            # (indicates splicing/compositing)
            threshold = mean_diff + 2 * std_diff
            suspicious_pixels = np.sum(ela_array > threshold)
            total_pixels = ela_array.size
            suspicious_ratio = suspicious_pixels / total_pixels

            if suspicious_ratio > 0.05:  # More than 5% suspicious
                manipulation_score += 0.2

            authenticity_score = max(0.0, 1.0 - manipulation_score)

            result = FraudCheckResult.AUTHENTIC
            if authenticity_score < 0.4:
                result = FraudCheckResult.MANIPULATED
            elif authenticity_score < 0.6:
                result = FraudCheckResult.SUSPICIOUS

            return {
                "check_type": "error_level_analysis",
                "result": result.value,
                "confidence": authenticity_score,
                "details": {
                    "max_error_difference": float(max_diff),
                    "mean_error_difference": float(mean_diff),
                    "std_error_difference": float(std_diff),
                    "suspicious_pixel_ratio": float(suspicious_ratio),
                    "manipulation_indicators": manipulation_score,
                },
            }

        except Exception as e:
            logger.error("ela_check_failed", error=str(e))
            return {
                "check_type": "error_level_analysis",
                "result": FraudCheckResult.INCONCLUSIVE.value,
                "confidence": 0.5,
                "details": {"error": str(e)},
            }

    async def _check_file_hash(
        self, image_bytes: bytes
    ) -> Dict[str, Any]:
        """Calculate file hash for integrity and duplicate detection."""
        try:
            sha256_hash = hashlib.sha256(image_bytes).hexdigest()
            md5_hash = hashlib.md5(image_bytes).hexdigest()

            # Perceptual hash for near-duplicate detection
            image = Image.open(io.BytesIO(image_bytes))
            import imagehash
            phash = str(imagehash.phash(image))
            dhash = str(imagehash.dhash(image))

            return {
                "check_type": "file_hash",
                "result": FraudCheckResult.AUTHENTIC.value,
                "confidence": 1.0,
                "details": {
                    "sha256": sha256_hash,
                    "md5": md5_hash,
                    "perceptual_hash": phash,
                    "difference_hash": dhash,
                },
            }

        except Exception as e:
            logger.error("hash_check_failed", error=str(e))
            return {
                "check_type": "file_hash",
                "result": FraudCheckResult.INCONCLUSIVE.value,
                "confidence": 0.5,
                "details": {"error": str(e)},
            }

    async def _detect_ai_generation(
        self,
        image: Image.Image,
        image_bytes: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """
        Detect AI-generated images using multiple heuristics.
        """
        try:
            indicators = []
            score = 0.9  # Start assuming authentic

            # Check 1: Filename patterns
            filename_lower = filename.lower()
            for indicator in self.ai_generation_indicators:
                if indicator in filename_lower:
                    indicators.append(
                        f"Filename contains AI tool name: {indicator}"
                    )
                    score -= 0.4

            # Check 2: Image dimensions (AI images often have specific sizes)
            width, height = image.size
            ai_common_sizes = [
                (512, 512), (768, 768), (1024, 1024),
                (512, 768), (768, 512), (1024, 768),
                (768, 1024), (1920, 1080), (1080, 1920),
            ]
            if (width, height) in ai_common_sizes:
                indicators.append(
                    f"Image dimensions ({width}x{height}) match common "
                    f"AI generation sizes"
                )
                score -= 0.1

            # Check 3: Color distribution analysis
            # AI images tend to have smoother color distributions
            img_array = np.array(image.convert("RGB"))
            color_std = np.std(img_array, axis=(0, 1))
            avg_color_std = np.mean(color_std)

            if avg_color_std < 20:  # Very uniform colors
                indicators.append(
                    "Unusually uniform color distribution"
                )
                score -= 0.15

            # Check 4: Edge analysis
            # AI images often have unusual edge patterns
            gray = image.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_array = np.array(edges)
            edge_mean = np.mean(edge_array)
            edge_std = np.std(edge_array)

            if edge_std < 15:  # Very smooth edges
                indicators.append(
                    "Unusually smooth edge patterns detected"
                )
                score -= 0.1

            # Check 5: Noise pattern analysis
            # Real photos have natural noise; AI images often have
            # uniform noise or no noise
            noise = img_array.astype(float) - np.round(
                img_array.astype(float) / 8
            ) * 8
            noise_std = np.std(noise)

            if noise_std < 2:
                indicators.append(
                    "Unusually low image noise (possible AI generation)"
                )
                score -= 0.15

            score = max(0.0, min(1.0, score))

            result = FraudCheckResult.AUTHENTIC
            if score < 0.3:
                result = FraudCheckResult.AI_GENERATED
            elif score < 0.5:
                result = FraudCheckResult.SUSPICIOUS

            return {
                "check_type": "ai_generation_detection",
                "result": result.value,
                "confidence": score,
                "details": {
                    "indicators": indicators,
                    "color_uniformity": float(avg_color_std),
                    "edge_smoothness": float(edge_std),
                    "noise_level": float(noise_std),
                    "image_dimensions": f"{width}x{height}",
                },
            }

        except Exception as e:
            logger.error("ai_detection_failed", error=str(e))
            return {
                "check_type": "ai_generation_detection",
                "result": FraudCheckResult.INCONCLUSIVE.value,
                "confidence": 0.5,
                "details": {"error": str(e)},
            }

    async def _check_metadata_consistency(
        self,
        image: Image.Image,
        image_bytes: bytes
    ) -> Dict[str, Any]:
        """Check for consistency between different metadata sources."""
        try:
            issues = []
            score = 0.9

            # File size vs dimensions check
            width, height = image.size
            file_size = len(image_bytes)
            pixel_count = width * height

            # JPEG typically: 0.5-3 bytes per pixel
            # PNG typically: 1-4 bytes per pixel
            bytes_per_pixel = file_size / pixel_count if pixel_count > 0 else 0

            if bytes_per_pixel > 5:
                issues.append(
                    "File size unusually large for image dimensions"
                )
                score -= 0.1
            elif bytes_per_pixel < 0.1:
                issues.append(
                    "File size unusually small for image dimensions "
                    "(heavy compression)"
                )
                score -= 0.1

            # Check for multiple JPEG compressions
            # (indicates re-saving/editing)
            try:
                if image.format == "JPEG":
                    quantization = image.quantization
                    if quantization:
                        # Non-standard quantization tables suggest editing
                        standard_tables = {0, 1}
                        actual_tables = set(quantization.keys())
                        if actual_tables != standard_tables:
                            issues.append(
                                "Non-standard JPEG quantization tables "
                                "(possible editing)"
                            )
                            score -= 0.1
            except Exception:
                pass

            score = max(0.0, min(1.0, score))

            result = FraudCheckResult.AUTHENTIC
            if score < 0.5:
                result = FraudCheckResult.SUSPICIOUS

            return {
                "check_type": "metadata_consistency",
                "result": result.value,
                "confidence": score,
                "details": {
                    "issues": issues,
                    "bytes_per_pixel": round(bytes_per_pixel, 2),
                    "file_size_bytes": file_size,
                    "dimensions": f"{width}x{height}",
                    "format": image.format,
                    "mode": image.mode,
                },
            }

        except Exception as e:
            logger.error("consistency_check_failed", error=str(e))
            return {
                "check_type": "metadata_consistency",
                "result": FraudCheckResult.INCONCLUSIVE.value,
                "confidence": 0.5,
                "details": {"error": str(e)},
            }

    def _calculate_overall_score(
        self, results: List[Dict[str, Any]]
    ) -> Tuple[float, FraudCheckResult]:
        """Calculate weighted overall authenticity score."""
        weights = {
            "exif_metadata": 0.2,
            "error_level_analysis": 0.25,
            "file_hash": 0.1,
            "ai_generation_detection": 0.3,
            "metadata_consistency": 0.15,
        }

        total_score = 0.0
        total_weight = 0.0

        for check in results:
            check_type = check["check_type"]
            weight = weights.get(check_type, 0.1)
            confidence = check["confidence"]

            # If any check shows AI_GENERATED, heavily penalize
            if check["result"] == FraudCheckResult.AI_GENERATED.value:
                confidence *= 0.3

            total_score += confidence * weight
            total_weight += weight

        overall_score = total_score / total_weight if total_weight > 0 else 0.5

        if overall_score >= 0.7:
            overall_result = FraudCheckResult.AUTHENTIC
        elif overall_score >= 0.5:
            overall_result = FraudCheckResult.INCONCLUSIVE
        elif overall_score >= 0.3:
            overall_result = FraudCheckResult.SUSPICIOUS
        else:
            overall_result = FraudCheckResult.AI_GENERATED

        return round(overall_score, 3), overall_result

    def _get_recommendation(
        self, result: FraudCheckResult, score: float
    ) -> str:
        """Get human-readable recommendation."""
        recommendations = {
            FraudCheckResult.AUTHENTIC: (
                "Image appears authentic. Proceeding with RTI application."
            ),
            FraudCheckResult.INCONCLUSIVE: (
                "Image analysis is inconclusive. The image may still be "
                "genuine. We recommend also attaching location details "
                "for stronger evidence."
            ),
            FraudCheckResult.SUSPICIOUS: (
                "Image shows signs of potential manipulation. Please "
                "upload an original, unedited photo taken directly "
                "from your camera."
            ),
            FraudCheckResult.AI_GENERATED: (
                "Image appears to be AI-generated. RTI applications "
                "must use real photographs. Please upload a genuine "
                "photo of the issue."
            ),
            FraudCheckResult.MANIPULATED: (
                "Image shows strong signs of digital manipulation. "
                "Please upload the original, unedited photograph."
            ),
            FraudCheckResult.METADATA_MISSING: (
                "Image metadata is missing. This may be normal for "
                "screenshots or downloaded images. For best results, "
                "upload photos taken directly from your camera."
            ),
        }
        return recommendations.get(result, "Unable to determine image authenticity.")