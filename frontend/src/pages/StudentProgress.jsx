import React,{useEffect,useState}from'react';
import api from'../api/axios';
import './faculty-tools.css';
export default function StudentProgress(){const[d,setD]=useState([]);useEffect(()=>{api.get('my-progress/').then(r=>setD(r.data.trend||[]))},[]);return <section className="app-page faculty-tools-page"><header className="page-heading"><div><p className="eyebrow">My progress</p><h1>Released exam history</h1></div></header><article className="tool-panel">{d.map(x=><div className="tool-list" key={x.exam_id}><div><p><strong>{x.exam_title} — {x.percentage}%</strong><small>{x.subject} · {x.score}/{x.total_marks}</small></p></div></div>)||'No released results yet.'}</article></section>}


