import { useCallback, useState } from 'react';

// Validation rules
const VALIDATION_RULES = {
  email: (value) => {
    if (!value) return 'Email is required';
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(value)) return 'Please enter a valid email address';
    return null;
  },
  password: (value, minLength = 6) => {
    if (!value) return 'Password is required';
    if (value.length < minLength) return `Password must be at least ${minLength} characters`;
    return null;
  },
  passwordStrength: (value) => {
    if (!value) return 'Password is required';
    const strength = {
      hasUpperCase: /[A-Z]/.test(value),
      hasLowerCase: /[a-z]/.test(value),
      hasNumbers: /\d/.test(value),
      hasSpecialChar: /[!@#$%^&*]/.test(value),
    };
    const meetsRequirements = Object.values(strength).filter(Boolean).length;
    if (meetsRequirements < 3) {
      return 'Password should include uppercase, lowercase, numbers, and special characters';
    }
    return null;
  },
  name: (value) => {
    if (!value) return 'Name is required';
    if (value.trim().length < 2) return 'Name must be at least 2 characters';
    return null;
  },
  url: (value) => {
    if (!value) return 'URL is required';
    try {
      new URL(value);
      return null;
    } catch {
      return 'Please enter a valid URL';
    }
  },
  phone: (value) => {
    if (!value) return 'Phone number is required';
    const phoneRegex = /^[\d\s\-\+\(\)]{10,}$/;
    if (!phoneRegex.test(value)) return 'Please enter a valid phone number';
    return null;
  },
  required: (value, fieldName = 'This field') => {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return `${fieldName} is required`;
    }
    return null;
  },
};

export function useFormValidation(initialValues = {}, onSubmit = null) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Validate a single field
  const validateField = useCallback((name, value, rules = {}) => {
    let error = null;

    if (rules.validate) {
      error = rules.validate(value);
    } else if (rules.type) {
      const rule = VALIDATION_RULES[rules.type];
      if (rule) {
        error = rule(value, rules.minLength);
      }
    }

    setErrors((prev) => ({
      ...prev,
      [name]: error,
    }));

    return error;
  }, []);

  // Validate all fields
  const validateForm = useCallback((fieldsRules = {}) => {
    const newErrors = {};
    let isValid = true;

    Object.keys(fieldsRules).forEach((fieldName) => {
      const error = validateField(fieldName, values[fieldName], fieldsRules[fieldName]);
      if (error) {
        newErrors[fieldName] = error;
        isValid = false;
      }
    });

    setErrors(newErrors);
    return isValid;
  }, [values, validateField]);

  // Handle field change
  const handleChange = useCallback((e) => {
    const { name, value, type, checked } = e.target;
    const newValue = type === 'checkbox' ? checked : value;

    setValues((prev) => ({
      ...prev,
      [name]: newValue,
    }));

    // Clear error when user starts typing
    if (errors[name]) {
      setErrors((prev) => ({
        ...prev,
        [name]: null,
      }));
    }
  }, [errors]);

  // Handle field blur
  const handleBlur = useCallback((e) => {
    const { name } = e.target;
    setTouched((prev) => ({
      ...prev,
      [name]: true,
    }));
  }, []);

  // Handle form submission
  const handleSubmit = useCallback(
    (fieldsRules = {}) => (e) => {
      e.preventDefault();
      setIsSubmitting(true);

      const isValid = validateForm(fieldsRules);

      if (isValid && onSubmit) {
        onSubmit(values);
      }

      setIsSubmitting(false);
      return isValid;
    },
    [validateForm, values, onSubmit]
  );

  // Reset form
  const resetForm = useCallback((newInitialValues = initialValues) => {
    setValues(newInitialValues);
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
  }, [initialValues]);

  // Set field value
  const setFieldValue = useCallback((name, value) => {
    setValues((prev) => ({
      ...prev,
      [name]: value,
    }));
  }, []);

  // Set field error
  const setFieldError = useCallback((name, error) => {
    setErrors((prev) => ({
      ...prev,
      [name]: error,
    }));
  }, []);

  return {
    values,
    errors,
    touched,
    isSubmitting,
    handleChange,
    handleBlur,
    handleSubmit,
    validateField,
    validateForm,
    resetForm,
    setFieldValue,
    setFieldError,
  };
}

export default useFormValidation;
