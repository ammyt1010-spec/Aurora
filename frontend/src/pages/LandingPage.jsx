import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowDownRight, ArrowRight, BarChart3, Check, ChevronRight, FileCheck2, LockKeyhole, Menu, QrCode, ShieldCheck, SlidersHorizontal, X } from 'lucide-react';

import { getRegistrationPolicy } from '../api/auth.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { BrandMark } from '../brand/BrandMark.jsx';
import AuroraProductPreview from './AuroraProductPreview.jsx';
import './LandingPage.css';

const steps = [
  { number: '01', title: 'Selecciona', text: 'Elige la versión corta o media de CENSOPAS-COPSOQ y prepara tu evaluación.', icon: SlidersHorizontal },
  { number: '02', title: 'Comparte', text: 'Genera un enlace o código QR para que tus trabajadores respondan de forma anónima.', icon: QrCode },
  { number: '03', title: 'Comprende', text: 'Observa la participación y explora resultados por dimensiones y segmentos.', icon: BarChart3 },
  { number: '04', title: 'Documenta', text: 'Prepara el informe técnico para revisión, firmas y decisiones de mejora.', icon: FileCheck2 },
];

const capabilities = [
  { icon: QrCode, tag: 'APLICACIÓN', title: 'Del instrumento al enlace, sin fricción', text: 'Configura la evaluación y comparte un acceso sencillo con la población invitada. Una sola experiencia para coordinar la aplicación.' },
  { icon: BarChart3, tag: 'ANÁLISIS', title: 'Una lectura que revela prioridades', text: 'Visualiza las dimensiones, filtra por área o sexo y compara señales para descubrir dónde conviene profundizar.' },
  { icon: FileCheck2, tag: 'INFORME', title: 'Del análisis a un expediente claro', text: 'Organiza resultados, interpretación y responsables en un informe descargable que tu equipo puede revisar y firmar.' },
];

function LandingBrand({ dark = false }) {
  return <span className={`aurora-landing__brand${dark ? ' aurora-landing__brand--dark' : ''}`}>
    <BrandMark decorative className="aurora-landing__brand-mark" />
    <span><strong>AURORA</strong><small>PROFESSIONAL</small></span>
  </span>;
}

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { status } = useAuth();
  const { data: policy } = useQuery({ queryKey: ['registration-policy'], queryFn: getRegistrationPolicy, retry: false });
  const registrationOpen = policy?.self_registration_enabled === true;
  const signedIn = status === 'authenticated';
  const primaryHref = signedIn ? '/colmena' : registrationOpen ? '/signup' : '/login';
  const primaryLabel = signedIn ? 'Ir a mi panel' : registrationOpen ? 'Crear cuenta empresarial' : 'Ingresar a AURORA';

  return <main className="aurora-landing" id="inicio">
    <div className="aurora-landing__hero-shell">
      <div className="aurora-landing__ambient aurora-landing__ambient--one" aria-hidden="true" />
      <div className="aurora-landing__ambient aurora-landing__ambient--two" aria-hidden="true" />
      <div className="aurora-landing__grid" aria-hidden="true" />
      <header className="aurora-landing__header aurora-landing__container">
        <Link to="/" aria-label="AURORA, ir al inicio"><LandingBrand /></Link>
        <button type="button" className="aurora-landing__menu-toggle" aria-expanded={menuOpen} aria-controls="aurora-navigation" aria-label={menuOpen ? 'Cerrar menú' : 'Abrir menú'} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={23} /> : <Menu size={23} />}</button>
        <nav id="aurora-navigation" className={`aurora-landing__nav${menuOpen ? ' is-open' : ''}`} aria-label="Navegación principal">
          <a href="#plataforma" onClick={() => setMenuOpen(false)}>Plataforma</a>
          <a href="#como-funciona" onClick={() => setMenuOpen(false)}>Cómo funciona</a>
          <a href="#instrumentos" onClick={() => setMenuOpen(false)}>Instrumentos</a>
          <div className="aurora-landing__nav-actions">
            <Link to={signedIn ? '/colmena' : '/login'} className="aurora-landing__nav-login">{signedIn ? 'Mi panel' : 'Ingresar'}</Link>
            {!signedIn && registrationOpen ? <Link to="/signup" className="aurora-landing__nav-cta">Crear cuenta <ArrowRight size={15} /></Link> : null}
          </div>
        </nav>
      </header>

      <section className="aurora-landing__hero aurora-landing__container" aria-labelledby="aurora-hero-title">
        <div className="aurora-landing__hero-copy">
          <div className="aurora-landing__eyebrow"><span className="aurora-landing__eyebrow-dot" /> Inteligencia para la salud ocupacional</div>
          <h1 id="aurora-hero-title">El riesgo que no se ve, <em>ahora se entiende.</em></h1>
          <p>AURORA convierte la evaluación psicosocial en un proceso claro: aplica el instrumento, comprende tus datos y prepara decisiones respaldadas por un informe técnico.</p>
          <div className="aurora-landing__hero-actions">
            <Link to={primaryHref} className="aurora-landing__button aurora-landing__button--primary">{primaryLabel}<ArrowRight size={19} /></Link>
            <a href="#plataforma" className="aurora-landing__button aurora-landing__button--ghost">Conocer la plataforma <ArrowDownRight size={18} /></a>
          </div>
          {!signedIn && registrationOpen ? <p className="aurora-landing__offer">Tu cuenta comienza con cuatro evaluaciones gratuitas.</p> : null}
          <div className="aurora-landing__hero-notes"><span><Check size={15} /> Instrumentos CENSOPAS-COPSOQ</span><span><Check size={15} /> Respuestas anónimas</span><span><Check size={15} /> Informes descargables</span></div>
        </div>
        <div className="aurora-landing__hero-visual">
          <div className="aurora-landing__visual-halo" aria-hidden="true" />
          <div className="aurora-landing__float-tag aurora-landing__float-tag--top"><span className="aurora-landing__float-icon"><BarChart3 size={17} /></span><span>Datos que orientan<br /><strong>decisiones concretas</strong></span></div>
          <AuroraProductPreview />
          <div className="aurora-landing__float-tag aurora-landing__float-tag--bottom"><span className="aurora-landing__float-icon aurora-landing__float-icon--violet"><ShieldCheck size={18} /></span><span>Lectura por segmentos<br /><strong>sin exponer personas</strong></span></div>
        </div>
      </section>
      <div className="aurora-landing__hero-bottom aurora-landing__container"><span>DE LA MEDICIÓN A LA ACCIÓN</span><span>Una experiencia para empresa, SST y gerencia</span><a href="#plataforma" aria-label="Descubrir la plataforma"><ArrowDownRight size={18} /></a></div>
    </div>

    <section className="aurora-landing__section aurora-landing__section--light" id="plataforma">
      <div className="aurora-landing__container">
        <div className="aurora-landing__section-intro"><span className="aurora-landing__kicker">UNA PLATAFORMA, TODO EL RECORRIDO</span><h2>Menos operación. <span>Más claridad.</span></h2><p>Desde la invitación hasta el informe, cada etapa está diseñada para que los equipos vean lo importante y avancen con confianza.</p></div>
        <div className="aurora-landing__capability-grid">
          {capabilities.map(({ icon: Icon, tag, title, text }, index) => <article className="aurora-landing__capability" key={title}>
            <div className={`aurora-landing__capability-icon aurora-landing__capability-icon--${index}`}><Icon size={25} strokeWidth={1.9} /></div>
            <span className="aurora-landing__capability-tag">{tag}</span><h3>{title}</h3><p>{text}</p><span className="aurora-landing__capability-line" aria-hidden="true" />
          </article>)}
        </div>
      </div>
    </section>

    <section className="aurora-landing__section aurora-landing__section--flow" id="como-funciona">
      <div className="aurora-landing__container">
        <div className="aurora-landing__section-intro aurora-landing__section-intro--center"><span className="aurora-landing__kicker">UN FLUJO NATURAL</span><h2>Cuatro pasos para <span>entender mejor.</span></h2><p>Un recorrido continuo, sin saltar entre herramientas ni perder el contexto de la evaluación.</p></div>
        <div className="aurora-landing__steps">
          {steps.map(({ number, title, text, icon: Icon }) => <article className="aurora-landing__step" key={number}>
            <div className="aurora-landing__step-top"><span>{number}</span><Icon size={22} strokeWidth={1.8} /></div><h3>{title}</h3><p>{text}</p>
          </article>)}
        </div>
      </div>
    </section>

    <section className="aurora-landing__section aurora-landing__section--instrument" id="instrumentos">
      <div className="aurora-landing__container aurora-landing__instrument-layout">
        <div className="aurora-landing__instrument-copy"><span className="aurora-landing__kicker">INSTRUMENTOS DISPONIBLES</span><h2>Empieza con el instrumento correcto.</h2><p>Hoy AURORA ofrece CENSOPAS-COPSOQ en versión corta y versión media. El catálogo crecerá sin complicar el proceso para tu empresa.</p><Link to={primaryHref} className="aurora-landing__text-link">{primaryLabel} <ArrowRight size={17} /></Link></div>
        <div className="aurora-landing__instrument-cards">
          <Link to={primaryHref} className="aurora-landing__instrument-card"><span className="aurora-landing__instrument-number">01 / CENSOPAS-COPSOQ</span><h3>Versión corta</h3><p>Una opción para iniciar la evaluación con el instrumento correspondiente a tu proceso.</p><span className="aurora-landing__instrument-arrow"><ChevronRight size={20} /></span></Link>
          <Link to={primaryHref} className="aurora-landing__instrument-card"><span className="aurora-landing__instrument-number">02 / CENSOPAS-COPSOQ</span><h3>Versión media</h3><p>Profundiza la lectura del entorno psicosocial con la versión disponible en la plataforma.</p><span className="aurora-landing__instrument-arrow"><ChevronRight size={20} /></span></Link>
        </div>
      </div>
    </section>

    <section className="aurora-landing__section aurora-landing__section--trust">
      <div className="aurora-landing__container aurora-landing__trust-layout"><div className="aurora-landing__trust-icon"><LockKeyhole size={31} strokeWidth={1.6} /></div><div><span className="aurora-landing__kicker">PERSONAS PRIMERO</span><h2>Una lectura útil sin perder de vista la confidencialidad.</h2><p>Las respuestas se recogen de forma anónima. La interpretación se presenta a nivel agregado para orientar decisiones organizacionales, no para identificar a una persona.</p></div><Link to={primaryHref} className="aurora-landing__button aurora-landing__button--dark">Comenzar ahora <ArrowRight size={18} /></Link></div>
    </section>

    <footer className="aurora-landing__footer"><div className="aurora-landing__container aurora-landing__footer-inner"><div><LandingBrand dark /><p>Inteligencia para decisiones más claras en salud ocupacional.</p></div><div className="aurora-landing__footer-links"><a href="#plataforma">Plataforma</a><a href="#como-funciona">Cómo funciona</a><Link to="/login">Ingresar</Link></div><span className="aurora-landing__copyright">© {new Date().getFullYear()} AURORA Professional</span></div></footer>
  </main>;
}
