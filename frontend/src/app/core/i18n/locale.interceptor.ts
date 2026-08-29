import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { TranslationService } from './translation.service';

export const localeInterceptor: HttpInterceptorFn = (request, next) => {
  const locale = inject(TranslationService).locale();
  return next(request.clone({ setHeaders: { 'Accept-Language': locale } }));
};
