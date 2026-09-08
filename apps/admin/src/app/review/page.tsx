"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiUrl, clearSession, getToken } from "@/lib/auth";

interface ReviewQueueItem {
  id: string;
  story_id: string;
  reason: string;
  status: string;
  created_at: string;
}

export default function ReviewQueuePage() {
  const router = useRouter();
  const [items, setItems] = useState<ReviewQueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    fetch(`${apiUrl()}/v1/admin/review-queue`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((response) => {
        if (!response.ok) {
          if (response.status === 401) {
            clearSession();
            router.replace("/login");
          }
          throw new Error("Failed to load review queue");
        }
        return response.json();
      })
      .then((body: ReviewQueueItem[]) => setItems(body))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load review queue"));
  }, [router]);

  return (
    <main>
      <h1>Review queue</h1>
      <p>
        <Link href="/">Back to admin home</Link>
      </p>
      {error ? <p role="alert">{error}</p> : null}
      {items === null ? (
        <p>Loading…</p>
      ) : items.length === 0 ? (
        <p>Nothing pending review.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Reason</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.reason}</td>
                <td>{new Date(item.created_at).toLocaleString()}</td>
                <td>
                  <Link href={`/review/${item.story_id}`}>Open</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
