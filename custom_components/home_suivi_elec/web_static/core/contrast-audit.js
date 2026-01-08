"use strict";
/**
 * ============================================
 * CONTRAST AUDIT - Analyseur de contraste WCAG
 * ============================================
 * 
 * Analyse automatiquement tous les éléments de la page
 * et détecte les problèmes de contraste selon les normes WCAG 2.1
 * 
 * Niveaux WCAG :
 * - AA : Ratio minimum 4.5:1 (texte normal), 3:1 (grand texte)
 * - AAA : Ratio minimum 7:1 (texte normal), 4.5:1 (grand texte)
 */

class ContrastAuditor {
    constructor(options = {}) {
        this.options = {
            threshold: options.threshold || 'AA', // 'AA' ou 'AAA'
            ignoreTransparent: options.ignoreTransparent !== false,
            ignoreHidden: options.ignoreHidden !== false,
            verbose: options.verbose || false,
            autoFix: options.autoFix || false
        };
        
        this.issues = [];
        this.stats = {
            total: 0,
            passed: 0,
            failed: 0,
            critical: 0,
            warning: 0
        };
    }

    /**
     * Convertit une couleur hex en RGB
     */
    hexToRgb(hex) {
        // Nettoyer le hex
        hex = hex.replace('#', '');
        
        // Format court (#fff)
        if (hex.length === 3) {
            hex = hex.split('').map(char => char + char).join('');
        }
        
        const r = parseInt(hex.substring(0, 2), 16);
        const g = parseInt(hex.substring(2, 4), 16);
        const b = parseInt(hex.substring(4, 6), 16);
        
        return [r, g, b];
    }

    /**
     * Convertit une couleur rgb/rgba en tableau [r,g,b]
     */
    rgbStringToArray(rgbString) {
        const match = rgbString.match(/\d+/g);
        if (!match || match.length < 3) return [0, 0, 0];
        return [parseInt(match[0]), parseInt(match[1]), parseInt(match[2])];
    }

    /**
     * Calcule la luminance relative d'une couleur
     */
    getLuminance(rgb) {
        const [r, g, b] = rgb.map(val => {
            val = val / 255;
            return val <= 0.03928
                ? val / 12.92
                : Math.pow((val + 0.055) / 1.055, 2.4);
        });
        
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }

    /**
     * Calcule le ratio de contraste entre deux couleurs
     */
    getContrastRatio(color1, color2) {
        // Convertir en RGB si nécessaire
        let rgb1, rgb2;
        
        if (color1.startsWith('#')) {
            rgb1 = this.hexToRgb(color1);
        } else if (color1.startsWith('rgb')) {
            rgb1 = this.rgbStringToArray(color1);
        } else {
            return 0;
        }
        
        if (color2.startsWith('#')) {
            rgb2 = this.hexToRgb(color2);
        } else if (color2.startsWith('rgb')) {
            rgb2 = this.rgbStringToArray(color2);
        } else {
            return 0;
        }
        
        const lum1 = this.getLuminance(rgb1);
        const lum2 = this.getLuminance(rgb2);
        
        const lighter = Math.max(lum1, lum2);
        const darker = Math.min(lum1, lum2);
        
        return (lighter + 0.05) / (darker + 0.05);
    }

    /**
     * Obtient la couleur de fond effective (en remontant dans le DOM)
     */
    getEffectiveBackgroundColor(element) {
        let el = element;
        let bgColor = window.getComputedStyle(el).backgroundColor;
        
        // Remonter dans le DOM jusqu'à trouver un fond non-transparent
        while ((bgColor === 'rgba(0, 0, 0, 0)' || bgColor === 'transparent') && el.parentElement) {
            el = el.parentElement;
            bgColor = window.getComputedStyle(el).backgroundColor;
        }
        
        // Si toujours transparent, utiliser blanc par défaut
        if (bgColor === 'rgba(0, 0, 0, 0)' || bgColor === 'transparent') {
            bgColor = 'rgb(255, 255, 255)';
        }
        
        return bgColor;
    }

    /**
     * Détermine si l'élément est un "grand texte" selon WCAG
     */
    isLargeText(element) {
        const styles = window.getComputedStyle(element);
        const fontSize = parseFloat(styles.fontSize);
        const fontWeight = styles.fontWeight;
        
        // 18pt (24px) ou 14pt (18.5px) en gras
        return fontSize >= 24 || (fontSize >= 18.5 && (fontWeight === 'bold' || parseInt(fontWeight) >= 700));
    }

    /**
     * Obtient le ratio minimum requis selon WCAG
     */
    getRequiredRatio(element) {
        const isLarge = this.isLargeText(element);
        
        if (this.options.threshold === 'AAA') {
            return isLarge ? 4.5 : 7;
        }
        // AA par défaut
        return isLarge ? 3 : 4.5;
    }

    /**
     * Génère un sélecteur CSS pour l'élément
     */
    getSelector(element) {
        if (element.id) {
            return `#${element.id}`;
        }
        
        const classes = Array.from(element.classList).join('.');
        if (classes) {
            return `${element.tagName.toLowerCase()}.${classes}`;
        }
        
        return element.tagName.toLowerCase();
    }

    /**
     * Suggère une couleur de texte corrigée
     */
    suggestTextColor(bgColor, targetRatio = 4.5) {
        const bgRgb = bgColor.startsWith('#') 
            ? this.hexToRgb(bgColor) 
            : this.rgbStringToArray(bgColor);
        
        const bgLuminance = this.getLuminance(bgRgb);
        
        // Fond sombre = texte clair
        if (bgLuminance < 0.5) {
            return {
                color: '#ffffff',
                description: 'Texte blanc pour fond sombre'
            };
        }
        // Fond clair = texte sombre
        else {
            return {
                color: '#000000',
                description: 'Texte noir pour fond clair'
            };
        }
    }

    /**
     * Lance l'audit sur tous les éléments
     */
    audit() {
        console.log('🔍 Démarrage de l\'audit de contraste...');
        
        const startTime = performance.now();
        this.issues = [];
        this.stats = { total: 0, passed: 0, failed: 0, critical: 0, warning: 0 };
        
        // Sélectionner tous les éléments avec du texte
        const elements = document.querySelectorAll('*');
        
        elements.forEach(element => {
            // Ignorer les éléments cachés si demandé
            if (this.options.ignoreHidden) {
                const styles = window.getComputedStyle(element);
                if (styles.display === 'none' || styles.visibility === 'hidden') {
                    return;
                }
            }
            
            // Ignorer les éléments sans texte
            const hasText = element.childNodes && Array.from(element.childNodes).some(
                node => node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0
            );
            
            if (!hasText) return;
            
            const styles = window.getComputedStyle(element);
            const color = styles.color;
            const bgColor = this.getEffectiveBackgroundColor(element);
            
            // Ignorer si transparent et option activée
            if (this.options.ignoreTransparent && 
                (bgColor === 'rgba(0, 0, 0, 0)' || bgColor === 'transparent')) {
                return;
            }
            
            this.stats.total++;
            
            const ratio = this.getContrastRatio(color, bgColor);
            const requiredRatio = this.getRequiredRatio(element);
            
            if (ratio < requiredRatio) {
                const severity = ratio < 3 ? 'critical' : 'warning';
                this.stats.failed++;
                this.stats[severity]++;
                
                const issue = {
                    element: element,
                    selector: this.getSelector(element),
                    text: element.textContent.trim().substring(0, 50),
                    color: color,
                    backgroundColor: bgColor,
                    ratio: ratio.toFixed(2),
                    required: requiredRatio,
                    severity: severity,
                    suggestion: this.suggestTextColor(bgColor, requiredRatio)
                };
                
                this.issues.push(issue);
                
                if (this.options.verbose) {
                    console.warn(`❌ ${issue.selector}`, issue);
                }
            } else {
                this.stats.passed++;
            }
        });
        
        const endTime = performance.now();
        const duration = (endTime - startTime).toFixed(2);
        
        console.log(`✅ Audit terminé en ${duration}ms`);
        this.printReport();
        
        return {
            issues: this.issues,
            stats: this.stats,
            duration: duration
        };
    }

    /**
     * Affiche le rapport d'audit
     */
    printReport() {
        console.log('\n📊 RAPPORT D\'AUDIT DE CONTRASTE\n');
        console.log(`Total d'éléments analysés : ${this.stats.total}`);
        console.log(`✅ Conformes : ${this.stats.passed} (${((this.stats.passed/this.stats.total)*100).toFixed(1)}%)`);
        console.log(`❌ Non-conformes : ${this.stats.failed} (${((this.stats.failed/this.stats.total)*100).toFixed(1)}%)`);
        console.log(`   🔴 Critique (ratio < 3) : ${this.stats.critical}`);
        console.log(`   🟡 Avertissement (ratio < 4.5) : ${this.stats.warning}`);
        
        if (this.issues.length > 0) {
            console.log('\n🔍 Problèmes détectés par sévérité:\n');
            console.table(this.issues.map(issue => ({
                Sélecteur: issue.selector,
                Texte: issue.text,
                'Ratio actuel': issue.ratio,
                'Ratio requis': issue.required,
                Sévérité: issue.severity,
                'Couleur suggérée': issue.suggestion.color
            })));
        }
    }

    /**
     * Exporte le rapport en JSON
     */
    exportJSON() {
        return {
            timestamp: new Date().toISOString(),
            theme: document.body.dataset.theme || 'unknown',
            threshold: this.options.threshold,
            stats: this.stats,
            issues: this.issues.map(issue => ({
                selector: issue.selector,
                text: issue.text,
                color: issue.color,
                backgroundColor: issue.backgroundColor,
                ratio: parseFloat(issue.ratio),
                required: issue.required,
                severity: issue.severity,
                suggestion: issue.suggestion
            }))
        };
    }

    /**
     * Télécharge le rapport en fichier JSON
     */
    downloadReport() {
        const report = this.exportJSON();
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `contrast-audit-${report.theme}-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log('📥 Rapport téléchargé');
    }
}

// Export pour utilisation dans d'autres modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ContrastAuditor;
}

// API globale pour utilisation dans la console
window.ContrastAuditor = ContrastAuditor;

// Fonction d'audit rapide pour la console
window.auditContrast = (options) => {
    const auditor = new ContrastAuditor(options);
    return auditor.audit();
};

console.log('✅ Contrast Auditor chargé. Utilisez: window.auditContrast()');
