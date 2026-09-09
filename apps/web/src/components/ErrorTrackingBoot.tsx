"use client";

import { useEffect } from "react";

import { installGlobalErrorTracking } from "@/lib/errorTracking";

export function ErrorTrackingBoot() {
  useEffect(() => {
    installGlobalErrorTracking();
  }, []);
  return null;
}
