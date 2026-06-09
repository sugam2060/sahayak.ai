import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface AccountProfile {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  created_at: string | null;
  last_login_at: string | null;
}

// ─── API Fetchers ────────────────────────────────────────────────────────────

async function fetchProfile(): Promise<AccountProfile> {
  const res = await fetch(`${API_BASE_URL}/api/account/profile`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load profile.');
  }
  return res.json();
}

async function patchName(full_name: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/account/name`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ full_name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update name.');
  }
}

async function patchPassword(payload: {
  current_password: string;
  new_password: string;
  confirm_password: string;
}): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/account/password`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update password.');
  }
}

async function postEmailChangeRequest(new_email: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/account/email/request-change`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_email }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to request email change.');
  }
}

async function postEmailChangeConfirm(token: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE_URL}/api/account/email/confirm/${token}`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Email verification failed.');
  }
  return res.json();
}

// ─── TanStack Query Hooks ─────────────────────────────────────────────────────

export function useAccountProfile() {
  return useQuery<AccountProfile>({
    queryKey: ['account', 'profile'],
    queryFn: fetchProfile,
    staleTime: 1000 * 60 * 5, // 5 min
  });
}

export function useUpdateName() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: patchName,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['account', 'profile'] }),
  });
}

export function useUpdatePassword() {
  return useMutation({ mutationFn: patchPassword });
}

export function useRequestEmailChange() {
  return useMutation({ mutationFn: postEmailChangeRequest });
}

export function useConfirmEmailChange() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: postEmailChangeConfirm,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['account', 'profile'] });
    },
  });
}

