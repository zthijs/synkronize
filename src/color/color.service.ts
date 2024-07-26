import { Injectable, Logger } from '@nestjs/common';
import Vibrant from 'node-vibrant';
import { ApiOperation } from '@nestjs/swagger';
import { Palette, Swatch } from '@/common/interfaces/color.interface';

@Injectable()
export class ColorService {
  private readonly logger = new Logger(ColorService.name);

  @ApiOperation({ summary: 'Get color palette from image URL' })
  async getColors(url: string): Promise<Palette> {
    try {
      return await Vibrant.from(url).getPalette() as Palette;
    } catch (error) {
      this.logger.error(`Failed to fetch colors from URL: ${error.message}`);
      throw new Error(`Failed to fetch colors from URL: ${error.message}`);
    }
  }

  @ApiOperation({ summary: 'Get dominant color from image URL' })
  async getDominantColor(url: string): Promise<Swatch> {
    try {
      const palette = await Vibrant.from(url).getPalette();
      return (
        palette.Vibrant ||
        palette.Muted ||
        palette.DarkVibrant ||
        palette.DarkMuted ||
        palette.LightVibrant ||
        palette.LightMuted
      );
    } catch (error) {
      this.logger.error(
        `Failed to fetch dominant color from URL: ${error.message}`,
      );
      throw new Error(
        `Failed to fetch dominant color from URL: ${error.message}`,
      );
    }
  }
}
