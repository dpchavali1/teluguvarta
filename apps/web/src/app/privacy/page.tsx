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
      <p>
        In the mobile app, optional usage analytics is off until you turn it on
        in Privacy &amp; delete account. If enabled, Google Firebase Analytics
        receives basic app interactions and its app-instance identifier. We do
        not send search text, story IDs, profile details, or notification
        content. You can turn analytics off again in the app; deleting your
        account also resets its analytics identifier.
      </p>
    </div>
  );
}
