"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Icon } from "./Icon";
import type { TopicOut } from "@/lib/api";

export function TopicBar({ topics, pathname }: { topics: TopicOut[]; pathname: string }) {
  const list = useRef<HTMLUListElement>(null);
  const [edges, setEdges] = useState({ overflow: false, start: true, end: true });

  useEffect(() => {
    const el = list.current;
    if (!el) return;
    const measure = () => {
      const nav = el.parentElement!;
      const style = getComputedStyle(nav);
      // Compare with the width available without buttons so a growing viewport
      // removes controls even when they currently squeeze the list.
      const available = nav.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
      setEdges({
        overflow: el.scrollWidth > available + 1,
        start: el.scrollLeft <= 1,
        end: el.scrollLeft + el.clientWidth >= el.scrollWidth - 1,
      });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    if (el.parentElement) observer.observe(el.parentElement);
    for (const item of el.children) observer.observe(item);
    el.addEventListener("scroll", measure, { passive: true });
    measure();
    return () => { observer.disconnect(); el.removeEventListener("scroll", measure); };
  }, [topics]);

  useEffect(() => {
    // Reveal the selected topic without scrolling the page vertically.
    const el = list.current;
    const active = el?.querySelector<HTMLElement>('[aria-current="page"]');
    if (el && active) el.scrollLeft += active.getBoundingClientRect().left - el.getBoundingClientRect().left;
  }, [pathname, topics]);

  function move(direction: number) {
    const el = list.current;
    if (!el) return;
    el.scrollBy({ left: direction * el.clientWidth * 0.75, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  return <nav className="topic-bar" aria-label="Topics">
    {edges.overflow && <button type="button" className="topic-bar__scroll topic-bar__scroll--back" aria-label="Previous topics" aria-controls="header-topics" disabled={edges.start} onClick={() => move(-1)}><Icon name="arrowRight" /></button>}
    <ul id="header-topics" className="topic-bar__list" ref={list}>
      {topics.map((topic) => {
        const href = `/topic/${topic.slug}`;
        return <li key={topic.slug}><Link href={href} className="topic-bar__link" aria-current={pathname === href ? "page" : undefined}>{topic.name}</Link></li>;
      })}
    </ul>
    {edges.overflow && <button type="button" className="topic-bar__scroll" aria-label="More topics" aria-controls="header-topics" disabled={edges.end} onClick={() => move(1)}><Icon name="arrowRight" /></button>}
  </nav>;
}
