"""
Security validation utilities for interface-first testing.

This module provides utilities for validating security requirements,
including authentication, authorization, encryption, and PII handling.
"""

from collections.abc import Callable
from dataclasses import dataclass
import time


@dataclass
class SecurityMetrics:
    """Security metrics for validation."""

    authentication_success_rate: float
    authorization_success_rate: float
    encryption_validation_passed: bool
    pii_detection_rate: float
    security_headers_present: int
    total_security_tests: int
    passed_security_tests: int
    validation_time_ms: float


@dataclass
class SecurityResult:
    """Result of security validation."""

    test_name: str
    passed: bool
    metrics: SecurityMetrics
    errors: list[str]
    warnings: list[str]
    recommendations: list[str]

    def add_error(self, error: str):
        """Add an error to the security result."""
        self.errors.append(error)
        self.passed = False

    def add_warning(self, warning: str):
        """Add a warning to the security result."""
        self.warnings.append(warning)

    def add_recommendation(self, recommendation: str):
        """Add a recommendation to the security result."""
        self.recommendations.append(recommendation)


class SecurityValidator:
    """Validator for security requirements."""

    def __init__(
        self,
        require_authentication: bool = True,
        require_authorization: bool = True,
        require_encryption: bool = True,
        require_pii_handling: bool = True,
    ):
        self.require_authentication = require_authentication
        self.require_authorization = require_authorization
        self.require_encryption = require_encryption
        self.require_pii_handling = require_pii_handling

    async def validate_authentication(
        self,
        test_function: Callable,
        valid_credentials: dict[str, str],
        invalid_credentials: dict[str, str],
    ) -> SecurityResult:
        """Test authentication requirements."""
        result = SecurityResult(
            test_name="authentication_validation",
            passed=True,
            metrics=SecurityMetrics(
                authentication_success_rate=0.0,
                authorization_success_rate=0.0,
                encryption_validation_passed=False,
                pii_detection_rate=0.0,
                security_headers_present=0,
                total_security_tests=0,
                passed_security_tests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()
        successful_auth = 0
        failed_auth = 0

        try:
            # Test with valid credentials
            try:
                await test_function(credentials=valid_credentials)
                successful_auth += 1
            except Exception as e:
                result.add_error(f"Valid credentials authentication failed: {str(e)}")
                failed_auth += 1

            # Test with invalid credentials
            try:
                await test_function(credentials=invalid_credentials)
                result.add_error(
                    "Invalid credentials authentication should have failed"
                )
                failed_auth += 1
            except Exception:
                # This is expected - invalid credentials should fail
                successful_auth += 1

            # Test with no credentials
            try:
                await test_function(credentials={})
                if self.require_authentication:
                    result.add_error("No credentials authentication should have failed")
                    failed_auth += 1
                else:
                    successful_auth += 1
            except Exception:
                if self.require_authentication:
                    # This is expected when authentication is required
                    successful_auth += 1
                else:
                    result.add_warning(
                        "No credentials authentication failed when not required"
                    )
                    failed_auth += 1

            # Calculate authentication success rate
            total_tests = successful_auth + failed_auth
            if total_tests > 0:
                result.metrics.authentication_success_rate = (
                    successful_auth / total_tests
                ) * 100
                result.metrics.total_security_tests = total_tests
                result.metrics.passed_security_tests = successful_auth

                # Validate authentication requirements
                if (
                    self.require_authentication
                    and result.metrics.authentication_success_rate < 100
                ):
                    result.add_error("Authentication requirements not met")

                # Add recommendations
                if result.metrics.authentication_success_rate < 90:
                    result.add_recommendation("Improve authentication reliability")

                if result.metrics.authentication_success_rate < 100:
                    result.add_recommendation("Review authentication implementation")

            else:
                result.add_error("No authentication tests completed")

        except Exception as e:
            result.add_error(f"Authentication validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_authorization(
        self,
        test_function: Callable,
        admin_credentials: dict[str, str],
        user_credentials: dict[str, str],
        restricted_resource: str,
    ) -> SecurityResult:
        """Test authorization requirements."""
        result = SecurityResult(
            test_name="authorization_validation",
            passed=True,
            metrics=SecurityMetrics(
                authentication_success_rate=0.0,
                authorization_success_rate=0.0,
                encryption_validation_passed=False,
                pii_detection_rate=0.0,
                security_headers_present=0,
                total_security_tests=0,
                passed_security_tests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()
        successful_authz = 0
        failed_authz = 0

        try:
            # Test admin access to restricted resource
            try:
                await test_function(
                    credentials=admin_credentials, resource=restricted_resource
                )
                successful_authz += 1
            except Exception as e:
                result.add_error(f"Admin authorization failed: {str(e)}")
                failed_authz += 1

            # Test user access to restricted resource
            try:
                await test_function(
                    credentials=user_credentials, resource=restricted_resource
                )
                result.add_error(
                    "User authorization should have failed for restricted resource"
                )
                failed_authz += 1
            except Exception:
                # This is expected - users should not access restricted resources
                successful_authz += 1

            # Test user access to public resource
            try:
                await test_function(credentials=user_credentials, resource="public")
                successful_authz += 1
            except Exception as e:
                result.add_warning(f"User access to public resource failed: {str(e)}")
                failed_authz += 1

            # Calculate authorization success rate
            total_tests = successful_authz + failed_authz
            if total_tests > 0:
                result.metrics.authorization_success_rate = (
                    successful_authz / total_tests
                ) * 100
                result.metrics.total_security_tests = total_tests
                result.metrics.passed_security_tests = successful_authz

                # Validate authorization requirements
                if (
                    self.require_authorization
                    and result.metrics.authorization_success_rate < 100
                ):
                    result.add_error("Authorization requirements not met")

                # Add recommendations
                if result.metrics.authorization_success_rate < 90:
                    result.add_recommendation("Improve authorization reliability")

                if result.metrics.authorization_success_rate < 100:
                    result.add_recommendation("Review authorization implementation")

            else:
                result.add_error("No authorization tests completed")

        except Exception as e:
            result.add_error(f"Authorization validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_encryption(
        self, test_function: Callable, sensitive_data: str
    ) -> SecurityResult:
        """Test data encryption requirements."""
        result = SecurityResult(
            test_name="encryption_validation",
            passed=True,
            metrics=SecurityMetrics(
                authentication_success_rate=0.0,
                authorization_success_rate=0.0,
                encryption_validation_passed=False,
                pii_detection_rate=0.0,
                security_headers_present=0,
                total_security_tests=0,
                passed_security_tests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()

        try:
            # Test data encryption
            encrypted_data = await test_function(data=sensitive_data, encrypt=True)

            # Validate encryption
            if encrypted_data == sensitive_data:
                result.add_error("Data was not encrypted")
            # Check if encrypted data is different from original
            elif len(encrypted_data) != len(sensitive_data):
                result.metrics.encryption_validation_passed = True
                result.metrics.passed_security_tests += 1
            else:
                result.add_warning(
                    "Encrypted data length same as original - may not be properly encrypted"
                )

            # Test data decryption
            try:
                decrypted_data = await test_function(data=encrypted_data, decrypt=True)
                if decrypted_data == sensitive_data:
                    result.metrics.encryption_validation_passed = True
                    result.metrics.passed_security_tests += 1
                else:
                    result.add_error("Data decryption failed")
            except Exception as e:
                result.add_error(f"Data decryption failed: {str(e)}")

            # Test encryption consistency
            encrypted_data_2 = await test_function(data=sensitive_data, encrypt=True)
            if encrypted_data != encrypted_data_2:
                result.metrics.encryption_validation_passed = True
                result.metrics.passed_security_tests += 1
            else:
                result.add_warning("Encryption is deterministic - may not be secure")

            # Validate encryption requirements
            if (
                self.require_encryption
                and not result.metrics.encryption_validation_passed
            ):
                result.add_error("Encryption requirements not met")

            # Add recommendations
            if not result.metrics.encryption_validation_passed:
                result.add_recommendation("Implement proper data encryption")

            if result.metrics.encryption_validation_passed:
                result.add_recommendation(
                    "Consider using stronger encryption algorithms"
                )

        except Exception as e:
            result.add_error(f"Encryption validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_pii_handling(
        self, test_function: Callable, pii_data: str, non_pii_data: str
    ) -> SecurityResult:
        """Test PII handling requirements."""
        result = SecurityResult(
            test_name="pii_handling_validation",
            passed=True,
            metrics=SecurityMetrics(
                authentication_success_rate=0.0,
                authorization_success_rate=0.0,
                encryption_validation_passed=False,
                pii_detection_rate=0.0,
                security_headers_present=0,
                total_security_tests=0,
                passed_security_tests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()

        try:
            # Test PII detection
            pii_detected = await test_function(data=pii_data, detect_pii=True)
            non_pii_detected = await test_function(data=non_pii_data, detect_pii=True)

            # Validate PII detection
            if pii_detected and not non_pii_detected:
                result.metrics.pii_detection_rate = 100.0
                result.metrics.passed_security_tests += 1
            elif pii_detected and non_pii_detected:
                result.add_warning("PII detection may be too sensitive")
                result.metrics.pii_detection_rate = 50.0
            elif not pii_detected and non_pii_detected:
                result.add_error("PII detection failed - PII not detected")
                result.metrics.pii_detection_rate = 0.0
            else:
                result.add_warning("PII detection may not be working correctly")
                result.metrics.pii_detection_rate = 0.0

            # Test PII redaction
            if pii_detected:
                redacted_data = await test_function(data=pii_data, redact_pii=True)
                if redacted_data != pii_data:
                    result.metrics.passed_security_tests += 1
                else:
                    result.add_error("PII redaction failed")

            # Test PII encryption
            if pii_detected:
                encrypted_pii = await test_function(data=pii_data, encrypt_pii=True)
                if encrypted_pii != pii_data:
                    result.metrics.passed_security_tests += 1
                else:
                    result.add_error("PII encryption failed")

            # Validate PII handling requirements
            if self.require_pii_handling and result.metrics.pii_detection_rate < 80:
                result.add_error("PII handling requirements not met")

            # Add recommendations
            if result.metrics.pii_detection_rate < 80:
                result.add_recommendation("Improve PII detection accuracy")

            if result.metrics.passed_security_tests < 2:
                result.add_recommendation(
                    "Implement proper PII redaction and encryption"
                )

        except Exception as e:
            result.add_error(f"PII handling validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_security_headers(
        self, test_function: Callable
    ) -> SecurityResult:
        """Test security headers requirements."""
        result = SecurityResult(
            test_name="security_headers_validation",
            passed=True,
            metrics=SecurityMetrics(
                authentication_success_rate=0.0,
                authorization_success_rate=0.0,
                encryption_validation_passed=False,
                pii_detection_rate=0.0,
                security_headers_present=0,
                total_security_tests=0,
                passed_security_tests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()

        try:
            # Test security headers
            headers = await test_function(get_headers=True)

            # Required security headers
            required_headers = [
                "X-Content-Type-Options",
                "X-Frame-Options",
                "X-XSS-Protection",
                "Strict-Transport-Security",
                "Content-Security-Policy",
            ]

            present_headers = 0
            for header in required_headers:
                if header in headers:
                    present_headers += 1
                    result.metrics.passed_security_tests += 1
                else:
                    result.add_warning(f"Missing security header: {header}")

            result.metrics.security_headers_present = present_headers
            result.metrics.total_security_tests = len(required_headers)

            # Validate security headers requirements
            if present_headers < len(required_headers):
                result.add_error("Security headers requirements not met")

            # Add recommendations
            if present_headers < len(required_headers):
                result.add_recommendation("Implement missing security headers")

            if present_headers == len(required_headers):
                result.add_recommendation(
                    "Consider additional security headers for enhanced protection"
                )

        except Exception as e:
            result.add_error(f"Security headers validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result

    async def validate_comprehensive_security(
        self,
        test_function: Callable,
        valid_credentials: dict[str, str],
        invalid_credentials: dict[str, str],
        admin_credentials: dict[str, str],
        user_credentials: dict[str, str],
        sensitive_data: str,
        pii_data: str,
        non_pii_data: str,
    ) -> SecurityResult:
        """Comprehensive security validation."""
        result = SecurityResult(
            test_name="comprehensive_security_validation",
            passed=True,
            metrics=SecurityMetrics(
                authentication_success_rate=0.0,
                authorization_success_rate=0.0,
                encryption_validation_passed=False,
                pii_detection_rate=0.0,
                security_headers_present=0,
                total_security_tests=0,
                passed_security_tests=0,
                validation_time_ms=0.0,
            ),
            errors=[],
            warnings=[],
            recommendations=[],
        )

        start_time = time.time()

        try:
            # Run all security validations
            auth_result = await self.validate_authentication(
                test_function, valid_credentials, invalid_credentials
            )
            authz_result = await self.validate_authorization(
                test_function, admin_credentials, user_credentials, "restricted"
            )
            encryption_result = await self.validate_encryption(
                test_function, sensitive_data
            )
            pii_result = await self.validate_pii_handling(
                test_function, pii_data, non_pii_data
            )
            headers_result = await self.validate_security_headers(test_function)

            # Aggregate results
            result.metrics.authentication_success_rate = (
                auth_result.metrics.authentication_success_rate
            )
            result.metrics.authorization_success_rate = (
                authz_result.metrics.authorization_success_rate
            )
            result.metrics.encryption_validation_passed = (
                encryption_result.metrics.encryption_validation_passed
            )
            result.metrics.pii_detection_rate = pii_result.metrics.pii_detection_rate
            result.metrics.security_headers_present = (
                headers_result.metrics.security_headers_present
            )

            # Aggregate total tests
            result.metrics.total_security_tests = (
                auth_result.metrics.total_security_tests
                + authz_result.metrics.total_security_tests
                + encryption_result.metrics.total_security_tests
                + pii_result.metrics.total_security_tests
                + headers_result.metrics.total_security_tests
            )

            result.metrics.passed_security_tests = (
                auth_result.metrics.passed_security_tests
                + authz_result.metrics.passed_security_tests
                + encryption_result.metrics.passed_security_tests
                + pii_result.metrics.passed_security_tests
                + headers_result.metrics.passed_security_tests
            )

            # Aggregate errors and warnings
            result.errors.extend(auth_result.errors)
            result.errors.extend(authz_result.errors)
            result.errors.extend(encryption_result.errors)
            result.errors.extend(pii_result.errors)
            result.errors.extend(headers_result.errors)

            result.warnings.extend(auth_result.warnings)
            result.warnings.extend(authz_result.warnings)
            result.warnings.extend(encryption_result.warnings)
            result.warnings.extend(pii_result.warnings)
            result.warnings.extend(headers_result.warnings)

            result.recommendations.extend(auth_result.recommendations)
            result.recommendations.extend(authz_result.recommendations)
            result.recommendations.extend(encryption_result.recommendations)
            result.recommendations.extend(pii_result.recommendations)
            result.recommendations.extend(headers_result.recommendations)

            # Overall security assessment
            if result.metrics.authentication_success_rate < 100:
                result.add_error("Authentication requirements not met")

            if result.metrics.authorization_success_rate < 100:
                result.add_error("Authorization requirements not met")

            if not result.metrics.encryption_validation_passed:
                result.add_error("Encryption requirements not met")

            if result.metrics.pii_detection_rate < 80:
                result.add_error("PII handling requirements not met")

            if result.metrics.security_headers_present < 5:
                result.add_error("Security headers requirements not met")

            # Add overall recommendations
            if (
                result.metrics.passed_security_tests
                < result.metrics.total_security_tests
            ):
                result.add_recommendation("Review and improve security implementation")

            if (
                result.metrics.passed_security_tests
                == result.metrics.total_security_tests
            ):
                result.add_recommendation(
                    "Consider additional security measures for enhanced protection"
                )

        except Exception as e:
            result.add_error(f"Comprehensive security validation failed: {str(e)}")

        result.metrics.validation_time_ms = (time.time() - start_time) * 1000
        return result
