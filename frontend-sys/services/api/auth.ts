import { SignupData, LoginData, LoginResponse } from '@/types/auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const loginUser = async (data: LoginData): Promise<LoginResponse> => {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(data),
  });

  const result = await response.json();

  if (!response.ok && result.success !== false) {
    throw new Error(result.detail || 'Login failed');
  }
  return result as LoginResponse;
};

export interface RegistrationResponse {
  organization_id: string;
  user_id: string;
  message: string;
}

export interface ApiError {
  detail: string;
}

export const registerUser = async (data: SignupData): Promise<RegistrationResponse> => {
  const payload = {
    org_name: data.organizationName,
    org_slug: data.organizationSlug,
    full_name: data.fullName,
    email: data.email,
    password: data.password,
  };

  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.detail || 'An error occurred during registration');
  }

  return result as RegistrationResponse;
};

export interface VerificationResponse {
  success: boolean;
  message: string;
}

export const verifyEmail = async (token: string): Promise<VerificationResponse> => {
  const response = await fetch(`${API_BASE_URL}/auth/verify/${token}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.detail || 'Verification failed');
  }

  return result as VerificationResponse;
};

export const logoutUser = async (): Promise<{ success: boolean; message: string }> => {
  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.detail || 'Logout failed');
  }

  return result;
};

export const getProfile = async (): Promise<{ success: boolean; user: LoginResponse }> => {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.detail || 'Failed to fetch user profile');
  }

  return result;
};
