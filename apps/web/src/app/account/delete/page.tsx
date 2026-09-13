"use client";

import { useState } from "react";

import { track } from "@/lib/analytics";

export default function DeleteAccountPage() {
  const [cleared, setCleared] = useState(false);

  function handleClear() {
    track("account_delete_request");
    try {
      window.localStorage.removeItem("tg_saved_stories");
    } catch {
      // storage disabled — nothing to clear
    }
    setCleared(true);
  }

  return (
    <div className="legal">
      <h1>Delete account</h1>
      <p>
        TTE does not currently require or offer account creation on
        the website — every story is readable without signing in, and saved
        stories live only in this browser&rsquo;s local storage.
      </p>
      <p>
        You can clear all saved stories on this device below. When account
        creation ships, this page will also delete your account and its data,
        as required by our privacy commitments.
      </p>
      <button type="button" onClick={handleClear}>
        Clear saved stories on this device
      </button>
      {cleared && <p role="status">Saved stories cleared on this device.</p>}
    </div>
  );
}
