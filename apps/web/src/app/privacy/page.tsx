import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <div className="legal">
      <h1>Privacy</h1>
      <p>You can read every story on TTE without creating an account.</p>
      <p>
        Saved stories are stored only in your browser&rsquo;s local storage on
        this device — they are not sent to us or linked to any account.
      </p>
      <p>
        If TTE account creation is enabled in the future, you will be
        able to delete your account and its data at any time from{" "}
        <a href="/account/delete">Delete account</a>, both in the app and on
        this website.
      </p>
      <p>
        We never infer sensitive attributes such as immigration or visa status
        from reading behavior — personalization is based only on preferences
        you explicitly choose.
      </p>
    </div>
  );
}
