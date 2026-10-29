/**
 * TimelineBar — the week clock under the map (services/timelineStore.js; one clock for every map view).
 * Play / pause, a scrubber over the current week, the clock ("Week 2 · Wed 14:00") and the speed in
 * simulated days per second. Motion "full" runs the clock smoothly; "reduced" / "off" step it in half days.
 */
import React, { useEffect } from 'react';
import {
  useTimeline, toggleTimeline, seekTimeline, setTimelineSpeed, setTimelineMotion, clockLabel, WEEKDAYS,
} from '../../services/timelineStore.js';
import { useMotionLevel } from '../../services/prefsStore.js';

const SPEEDS = [1, 2, 7];

export default function TimelineBar({ summary = null }) {
  const { day, playing, speed } = useTimeline();
  const motion = useMotionLevel();
  useEffect(() => { setTimelineMotion(motion); }, [motion]);
  const week = Math.floor(day / 7);
  const inWeek = day - week * 7;

  return (
    <div className="tl-bar" role="group" aria-label="Simulation clock">
      <button type="button" className="tl-play" onClick={toggleTimeline} aria-pressed={playing}
        aria-label={playing ? 'Pause the clock' : 'Play the clock'} title={playing ? 'Pause (vessels hold position)' : 'Play: vessels sail their schedules'}>
        {playing ? '❚❚' : '▶'}
      </button>
      <span className="tl-clock" aria-live="off">{clockLabel(day)}</span>
      <div className="tl-track">
        <input type="range" min={0} max={7} step={0.05} value={inWeek} aria-label="Day of the week"
          aria-valuetext={clockLabel(day)} onChange={(e) => seekTimeline(week * 7 + Number(e.target.value))} />
        <div className="tl-ticks" aria-hidden="true">{WEEKDAYS.map((d) => <span key={d}>{d}</span>)}</div>
      </div>
      <div className="tl-speed" role="radiogroup" aria-label="Clock speed">
        {SPEEDS.map((s) => (
          <button key={s} type="button" role="radio" aria-checked={speed === s} className={speed === s ? 'is-on' : ''}
            onClick={() => setTimelineSpeed(s)} title={`${s} simulated day${s === 1 ? '' : 's'} per second`}>{s}d/s</button>
        ))}
      </div>
      {week > 0 && <button type="button" className="tl-reset" onClick={() => seekTimeline(0)} title="Back to week 1, Monday 00:00">⟲</button>}
      {summary && <span className="tl-summary">{summary}{motion !== 'full' ? ' · stepped (motion setting)' : ''}</span>}
    </div>
  );
}
