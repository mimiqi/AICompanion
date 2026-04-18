/**
 * Tiny REST client for the AICompanion `/api/companion/*` endpoints.
 *
 * The base URL is taken from the `WebSocketContext` so the panels
 * automatically follow whatever backend the user picked.
 */

import { useCallback } from 'react';
import { useWebSocket } from '@/context/websocket-context';

export interface Todo {
  id: number;
  title: string;
  notes: string | null;
  status: 'pending' | 'completed';
  due_at: number | null;
  created_at: number;
  updated_at: number;
  completed_at: number | null;
}

export interface MailSummary {
  uid: string;
  subject: string;
  sender: string;
  date: string | null;
  snippet: string;
  is_unread: boolean;
}

export interface MailDetail extends MailSummary {
  body: string;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText} ${text}`);
  }
  return (await res.json()) as T;
}

export function useCompanionApi() {
  const { baseUrl } = useWebSocket();

  const listTodos = useCallback(
    async (status: 'pending' | 'completed' | 'all' = 'pending') => {
      const res = await fetch(
        `${baseUrl}/api/companion/todos?status=${status}&limit=100`,
      );
      const data = await jsonOrThrow<{ ok: boolean; todos: Todo[] }>(res);
      return data.todos;
    },
    [baseUrl],
  );

  const createTodo = useCallback(
    async (input: { title: string; notes?: string; due_at?: number }) => {
      const res = await fetch(`${baseUrl}/api/companion/todos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      });
      const data = await jsonOrThrow<{ ok: boolean; todo: Todo }>(res);
      return data.todo;
    },
    [baseUrl],
  );

  const updateTodo = useCallback(
    async (id: number, patch: Partial<Pick<Todo, 'title' | 'notes' | 'due_at' | 'status'>>) => {
      const res = await fetch(`${baseUrl}/api/companion/todos/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
      const data = await jsonOrThrow<{ ok: boolean; todo: Todo }>(res);
      return data.todo;
    },
    [baseUrl],
  );

  const deleteTodo = useCallback(
    async (id: number) => {
      const res = await fetch(`${baseUrl}/api/companion/todos/${id}`, {
        method: 'DELETE',
      });
      await jsonOrThrow<{ ok: boolean }>(res);
    },
    [baseUrl],
  );

  const listRecentMail = useCallback(
    async (unreadOnly: boolean = true, limit: number = 20) => {
      const res = await fetch(
        `${baseUrl}/api/companion/mail/recent?unread_only=${unreadOnly}&limit=${limit}`,
      );
      const data = await jsonOrThrow<{ ok: boolean; emails: MailSummary[] }>(res);
      return data.emails;
    },
    [baseUrl],
  );

  const getMailDetail = useCallback(
    async (uid: string) => {
      const res = await fetch(
        `${baseUrl}/api/companion/mail/${encodeURIComponent(uid)}`,
      );
      const data = await jsonOrThrow<{ ok: boolean; email: MailDetail }>(res);
      return data.email;
    },
    [baseUrl],
  );

  return {
    listTodos,
    createTodo,
    updateTodo,
    deleteTodo,
    listRecentMail,
    getMailDetail,
  };
}
